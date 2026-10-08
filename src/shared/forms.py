from collections.abc import Sequence
from contextlib import contextmanager

from django import forms
from django.core.exceptions import ValidationError
from django.utils.functional import Promise

from shared.exceptions import Error


class TypedForm[TCleanedParams](forms.Form):
    """Form that maps cleaned data to the parameters of one use case."""

    @property
    def cleaned_params(self) -> TCleanedParams:
        raise NotImplementedError

    @staticmethod
    def _validation_error(error: Error) -> ValidationError:
        message = getattr(type(error), 'message', None)
        if not isinstance(message, str | Promise) or not message:
            message = error.code

        return ValidationError(message, code=error.code, params=error.details)

    def add_error(self, field, error):
        if isinstance(error, Error):
            error = self._validation_error(error)
        elif (
            isinstance(error, Sequence)
            and not isinstance(error, (str, bytes))
            and all(isinstance(item, Error) for item in error)
        ):
            if not error:
                return

            error = [self._validation_error(item) for item in error]

        super().add_error(field, error)

    @contextmanager
    def _capture(self, field):
        try:
            yield
        except (ValidationError, Error) as error:
            self.add_error(field, error)

    def _clean_fields(self):
        for name, bound_field in self._bound_items():
            with self._capture(name):
                self.cleaned_data[name] = bound_field.field._clean_bound_field(  # noqa: SLF001
                    bound_field,
                )
                clean_field = getattr(self, f'clean_{name}', None)
                if clean_field is not None:
                    self.cleaned_data[name] = clean_field()

    def _clean_form(self):
        with self._capture(None):
            cleaned_data = self.clean()
            if cleaned_data is not None:
                self.cleaned_data = cleaned_data
