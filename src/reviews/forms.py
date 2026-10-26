from django import forms

from reviews.models import COMMENT_MAX_LENGTH, MAX_SCORE, MIN_SCORE


class ReviewForm(forms.Form):
    score = forms.IntegerField(
        min_value=MIN_SCORE,
        max_value=MAX_SCORE,
        error_messages={
            'required': 'Elegí una puntuación de 1 a 5 estrellas.',
            'invalid': 'Elegí una puntuación de 1 a 5 estrellas.',
            'min_value': 'Elegí una puntuación de 1 a 5 estrellas.',
            'max_value': 'Elegí una puntuación de 1 a 5 estrellas.',
        },
    )

    comment = forms.CharField(
        required=False,
        max_length=COMMENT_MAX_LENGTH,
        strip=True,
        error_messages={
            'max_length': (
                f'El comentario puede tener hasta {COMMENT_MAX_LENGTH} caracteres.'
            ),
        },
        widget=forms.Textarea(
            attrs={
                'rows': 3,
                'maxlength': COMMENT_MAX_LENGTH,
                'placeholder': 'Un comentario corto (opcional)',
            },
        ),
    )
