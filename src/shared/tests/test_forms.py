from dataclasses import dataclass

import pytest
from django import forms
from django.core.exceptions import ValidationError

from shared.exceptions import Error
from shared.forms import TypedForm

MINIMUM_NAME_LENGTH = 3


@dataclass(frozen=True)
class TooShortError(Error):
    minimum: int


@dataclass(frozen=True)
class OutOfRangeError(Error):
    minimum: int
    maximum: int


@dataclass(frozen=True)
class ProfileParams:
    name: str


class ProfileForm(TypedForm[ProfileParams]):
    name = forms.CharField()

    @property
    def cleaned_params(self) -> ProfileParams:
        return ProfileParams(name=self.cleaned_data['name'])

    def clean_name(self):
        name = self.cleaned_data['name']
        if len(name) < MINIMUM_NAME_LENGTH:
            raise TooShortError(minimum=MINIMUM_NAME_LENGTH)
        return name


def test_valid_form_exposes_cleaned_params():
    form = ProfileForm(data={'name': 'Ana'})

    assert form.is_valid()
    assert form.cleaned_params == ProfileParams(name='Ana')


def test_field_clean_keeps_domain_error_code_and_details():
    form = ProfileForm(data={'name': 'Al'})

    assert not form.is_valid()
    error = form.errors['name'].as_data()[0]
    assert error.code == 'TooShortError'
    assert error.params == {'minimum': 3}


def test_form_clean_keeps_domain_error_code_and_details():
    class RejectingForm(ProfileForm):
        def clean(self):
            raise OutOfRangeError(minimum=1, maximum=2)

    form = RejectingForm(data={'name': 'Ana'})

    assert not form.is_valid()
    error = form.non_field_errors().as_data()[0]
    assert error.code == 'OutOfRangeError'
    assert error.params == {'minimum': 1, 'maximum': 2}


def test_add_error_accepts_several_domain_errors():
    form = ProfileForm(data={'name': 'Ana'})
    form.is_valid()

    errors = [
        TooShortError(minimum=MINIMUM_NAME_LENGTH),
        OutOfRangeError(minimum=1, maximum=2),
    ]
    form.add_error('name', errors)

    codes = [error.code for error in form.errors['name'].as_data()]
    assert codes == ['TooShortError', 'OutOfRangeError']


def test_add_error_ignores_an_empty_sequence():
    form = ProfileForm(data={'name': 'Ana'})
    assert form.is_valid()

    form.add_error('name', [])

    assert form.is_valid()


def test_django_validation_error_still_marks_the_field():
    class InvalidNameForm(ProfileForm):
        def clean_name(self):
            message = 'invalid'
            raise ValidationError(message, code='invalid_name')

    form = InvalidNameForm(data={'name': 'Ana'})

    assert not form.is_valid()
    assert form.errors['name'].as_data()[0].code == 'invalid_name'


def test_cleaned_params_must_be_implemented():
    form = TypedForm(data={})

    with pytest.raises(NotImplementedError):
        _ = form.cleaned_params
