FROM python:3.13.15-slim-bookworm

ARG DJANGO_SETTINGS_MODULE=app.settings.production
ARG SECRET_KEY=build-only-not-used-at-runtime
ARG ALLOWED_HOSTS=localhost
ARG HOSTNAME=localhost
ARG DATABASE_URL=postgres://build:build@localhost:5432/build

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_NO_CACHE=1 \
    PYTHONPATH=/app/src \
    DJANGO_SETTINGS_MODULE=${DJANGO_SETTINGS_MODULE} \
    SECRET_KEY=${SECRET_KEY} \
    ALLOWED_HOSTS=${ALLOWED_HOSTS} \
    HOSTNAME=${HOSTNAME} \
    DATABASE_URL=${DATABASE_URL}

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        binutils \
        gdal-bin \
        libgdal-dev \
        libgeos-dev \
        libmagic1 \
        libproj-dev \
        libsqlite3-mod-spatialite

COPY --from=ghcr.io/astral-sh/uv:0.12.22 /uv /uvx /bin/

COPY pyproject.toml uv.lock ./
ARG UV_SYNC_ARGS=--no-dev
RUN uv sync --frozen ${UV_SYNC_ARGS} --no-install-project

COPY src ./src

RUN uv run python src/manage.py tailwind build

RUN uv run --no-sync python src/manage.py collectstatic --noinput \
    && useradd --create-home app \
    && chown -R app:app media staticfiles

COPY docker-entrypoint.sh /docker-entrypoint.sh
COPY bin /app/bin
RUN chmod +x /docker-entrypoint.sh /app/bin/prepare-release /app/bin/start-web

EXPOSE 8000

ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["/app/bin/start-web"]
