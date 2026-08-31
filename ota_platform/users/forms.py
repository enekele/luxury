from allauth.account.forms import SignupForm
from django import forms


class CustomSignupForm(SignupForm):
    """Collect and persist the profile fields shown on the signup page."""

    first_name = forms.CharField(max_length=150, label='First name')
    last_name = forms.CharField(max_length=150, label='Last name')
    phone = forms.CharField(max_length=20, required=False, label='Phone number')
    terms = forms.BooleanField(
        required=True,
        label='I agree to the Terms of Service and Privacy Policy.',
        error_messages={'required': 'You must accept the Terms of Service and Privacy Policy.'},
    )
    newsletter = forms.BooleanField(
        required=False,
        label='Send me exclusive travel deals and event previews.',
    )

    def save(self, request):
        user = super().save(request)
        user.first_name = self.cleaned_data['first_name'].strip()
        user.last_name = self.cleaned_data['last_name'].strip()
        user.phone = self.cleaned_data.get('phone', '').strip()
        user.promotional_emails = self.cleaned_data.get('newsletter', False)
        user.save(
            update_fields=[
                'first_name',
                'last_name',
                'phone',
                'promotional_emails',
            ]
        )
        return user
