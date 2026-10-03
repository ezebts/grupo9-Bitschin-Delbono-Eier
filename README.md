# grupo9-Bitschin-Delbono-Eier

App Web en Django 6. Desarrollo local con Docker Compose + `uv`.

El código del proyecto debe ser escrito (y debemos mantenerlo) en Inglés. Sólo los textos/contenidos del frontend (o assets estáticos, entradas y salidas de la app, etc.) pueden estar en un idioma diferente, para estos vamos a usar Español (Argentina) por defecto.

Separar las implementaciónes en diferentes contextos (diferentes django apps). Por ejemplo: `src.cuentas`, `src.pagos`, `src.pedidos`, etc.

Todo lo que tengan en común (ej: utilidades varias) va en `src.shared` que es el módulo compartido importado por todos los demás.

## Requisitos

- [uv](https://docs.astral.sh/uv/)
- Docker + Docker Compose

## Arranque

```bash
make setup   # crea .env si falta e instala deps
make up      # levanta Postgres + la app para arrancar a desarrollar
```

SERVER URL [http://localhost:8000](http://localhost:8000).

## Comandos útiles

| Comando | Descripción |
|---|---|
| `make up` | Build + start de `development.yaml` |
| `make down` | Baja los containers |
| `make migrations` | `makemigrations` adentro de `web` |
| `make migrate` | `migrate` adentro de `web` |
| `make tests` | `pytest` adentro de `web` |

## Config

- Variables de entorno: Copiar `.env.example` a `.env`, el setup ya lo hace automático y configurar todo en `.env`.

## Frontend Stack

- HTMX
- Alpine.js
- Tailwind CSS 4
- DaisyUI 5
