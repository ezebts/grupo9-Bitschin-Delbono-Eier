from django import forms

from accounts.models import SearchRadius


class SearchRadiusInput(forms.NumberInput):
    """Preset distances with a free kilometers input for any other one."""

    template_name = 'accounts/_search_radius.html'

    def __init__(self, *, allow_empty=False, select_class='w-full', input_class=''):
        super().__init__()
        self.allow_empty = allow_empty
        self.select_class = select_class
        self.input_class = input_class

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        value = context['widget']['value'] or ''
        presets = [str(km) for km in SearchRadius.presets]
        context['widget'].update(
            presets=presets,
            choice=value if value in presets or not value else 'other',
            allow_empty=self.allow_empty,
            select_class=self.select_class,
            input_class=self.input_class,
            min_km=SearchRadius.min_km,
            max_km=SearchRadius.max_km,
        )
        return context
