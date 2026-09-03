from datetime import timedelta

from django import forms
from django.conf import settings
from django.utils import timezone
from djmoney.money import Money

from core.models import City, Country
from hotels.models import RoomType


class RoomTypeForm(forms.ModelForm):
    price_amount = forms.DecimalField(
        min_value=0,
        max_digits=10,
        decimal_places=2,
        label='Price per night',
    )
    currency = forms.ChoiceField(label='Currency')
    amenities = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'rows': 3}),
        help_text='Enter one amenity per line or separate amenities with commas.',
    )

    class Meta:
        model = RoomType
        fields = (
            'name',
            'description',
            'max_occupancy',
            'size_sqm',
            'bed_type',
            'total_rooms',
            'available_rooms',
            'is_active',
        )
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'max_occupancy': forms.NumberInput(attrs={'min': 1}),
            'size_sqm': forms.NumberInput(attrs={'min': 1}),
            'total_rooms': forms.NumberInput(attrs={'min': 1}),
            'available_rooms': forms.NumberInput(attrs={'min': 0}),
        }

    def __init__(self, *args, hotel, **kwargs):
        super().__init__(*args, **kwargs)
        self.hotel = hotel
        currencies = getattr(settings, 'CURRENCIES', ['USD'])
        self.fields['currency'].choices = [(code, code) for code in currencies]
        self.fields['is_active'].label = 'Category available to customers'
        self.fields['max_occupancy'].min_value = 1
        self.fields['size_sqm'].min_value = 1
        self.fields['total_rooms'].min_value = 1
        self.fields['available_rooms'].min_value = 0

        if self.instance and self.instance.pk:
            self.initial.setdefault('price_amount', self.instance.price_per_night.amount)
            self.initial.setdefault('currency', str(self.instance.price_per_night.currency))
            self.initial.setdefault(
                'amenities',
                '\n'.join(self.instance.amenities or []),
            )
        else:
            self.initial.setdefault('price_amount', hotel.price_per_night.amount)
            self.initial.setdefault('currency', str(hotel.price_per_night.currency))
            self.initial.setdefault('available_rooms', 1)
            self.initial.setdefault('total_rooms', 1)
            self.initial.setdefault('is_active', True)

        self.order_fields(
            [
                'name',
                'description',
                'price_amount',
                'currency',
                'max_occupancy',
                'total_rooms',
                'available_rooms',
                'size_sqm',
                'bed_type',
                'amenities',
                'is_active',
            ]
        )
        _style_fields(self)

    def clean_name(self):
        name = self.cleaned_data['name'].strip()
        existing = RoomType.objects.filter(hotel=self.hotel, name__iexact=name)
        if self.instance and self.instance.pk:
            existing = existing.exclude(pk=self.instance.pk)
        if existing.exists():
            raise forms.ValidationError(
                'This hotel already has a room category with that name.'
            )
        return name

    def clean_amenities(self):
        value = self.cleaned_data.get('amenities', '')
        normalized = value.replace(',', '\n')
        return [item.strip() for item in normalized.splitlines() if item.strip()]

    def clean(self):
        cleaned_data = super().clean()
        total_rooms = cleaned_data.get('total_rooms')
        available_rooms = cleaned_data.get('available_rooms')
        if (
            total_rooms is not None
            and available_rooms is not None
            and available_rooms > total_rooms
        ):
            self.add_error(
                'available_rooms',
                'Available rooms cannot exceed the total number of rooms.',
            )
        return cleaned_data

    def save(self, commit=True):
        room_type = super().save(commit=False)
        room_type.hotel = self.hotel
        room_type.price_per_night = Money(
            self.cleaned_data['price_amount'],
            self.cleaned_data['currency'],
        )
        room_type.amenities = self.cleaned_data['amenities']
        if commit:
            room_type.save()
        return room_type


class RoomAvailabilityForm(forms.Form):
    room_type = forms.ModelChoiceField(
        queryset=RoomType.objects.none(),
        label='Room category',
    )
    start_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date'}),
    )
    end_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date'}),
    )
    available_rooms = forms.IntegerField(
        min_value=0,
        label='Rooms available each day',
    )
    price_amount = forms.DecimalField(
        min_value=0,
        max_digits=10,
        decimal_places=2,
        label='Nightly rate',
    )
    currency = forms.ChoiceField(label='Currency')

    def __init__(self, *args, hotel, **kwargs):
        super().__init__(*args, **kwargs)
        self.hotel = hotel
        self.fields['room_type'].queryset = hotel.room_types.filter(
            is_active=True
        ).order_by('name')
        currencies = getattr(settings, 'CURRENCIES', ['USD'])
        self.fields['currency'].choices = [(code, code) for code in currencies]
        today = timezone.localdate()
        self.initial.setdefault('start_date', today)
        self.initial.setdefault('end_date', today + timedelta(days=29))
        self.initial.setdefault('available_rooms', 1)
        self.initial.setdefault('price_amount', hotel.price_per_night.amount)
        self.initial.setdefault('currency', str(hotel.price_per_night.currency))
        self.fields['start_date'].widget.attrs['min'] = today.isoformat()
        self.fields['end_date'].widget.attrs['min'] = today.isoformat()
        _style_fields(self)

    def clean(self):
        cleaned_data = super().clean()
        room_type = cleaned_data.get('room_type')
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        available_rooms = cleaned_data.get('available_rooms')

        if start_date and start_date < timezone.localdate():
            self.add_error('start_date', 'Availability cannot start in the past.')
        if start_date and end_date and end_date < start_date:
            self.add_error('end_date', 'End date must be on or after the start date.')
        if start_date and end_date and (end_date - start_date).days > 365:
            self.add_error('end_date', 'Update at most 366 days at a time.')
        if (
            room_type
            and available_rooms is not None
            and available_rooms > room_type.total_rooms
        ):
            self.add_error(
                'available_rooms',
                f'This category has only {room_type.total_rooms} total rooms.',
            )
        return cleaned_data


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
        elif isinstance(field.widget, forms.Select):
            field.widget.attrs['class'] = 'form-select'
        else:
            field.widget.attrs['class'] = 'form-control'
