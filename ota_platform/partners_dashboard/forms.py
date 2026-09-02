from django import forms

from core.models import City, Country


class CountryForm(forms.ModelForm):
    class Meta:
        model = Country
        fields = ('name', 'code', 'currency', 'timezone', 'is_active')
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': 'e.g. Nigeria'}),
            'timezone': forms.TextInput(attrs={'placeholder': 'e.g. Africa/Lagos'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['currency'].required = False
        _style_fields(self)

    def clean_name(self):
        name = self.cleaned_data['name'].strip()
        if Country.objects.filter(name__iexact=name).exists():
            raise forms.ValidationError('This country already exists.')
        return name

    def clean_code(self):
        code = self.cleaned_data['code']
        if Country.objects.filter(code=code).exists():
            raise forms.ValidationError('This country code already exists.')
        return code


class CityForm(forms.ModelForm):
    class Meta:
        model = City
        fields = (
            'name',
            'country',
            'latitude',
            'longitude',
            'is_popular',
            'is_active',
        )
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': 'e.g. Abuja'}),
            'latitude': forms.NumberInput(attrs={'step': '0.00000001'}),
            'longitude': forms.NumberInput(attrs={'step': '0.00000001'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['country'].queryset = Country.objects.filter(
            is_active=True
        ).order_by('name')
        _style_fields(self)

    def clean(self):
        cleaned_data = super().clean()
        name = (cleaned_data.get('name') or '').strip()
        country = cleaned_data.get('country')

        if name:
            cleaned_data['name'] = name
        if name and country and City.objects.filter(
            name__iexact=name,
            country=country,
        ).exists():
            self.add_error('name', 'This city already exists in the selected country.')

        return cleaned_data


def _style_fields(form):
    for field in form.fields.values():
        if isinstance(field.widget, forms.CheckboxInput):
            field.widget.attrs['class'] = 'form-check-input'
        else:
            field.widget.attrs['class'] = 'form-control'
