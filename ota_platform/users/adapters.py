from allauth.account.adapter import DefaultAccountAdapter
from django.urls import reverse


class AccountAdapter(DefaultAccountAdapter):
    """Send active partners to their dashboard after a normal sign-in."""

    def get_login_redirect_url(self, request):
        partner = getattr(request.user, 'partner_profile', None)
        if partner is not None and partner.is_active:
            return reverse('partners_dashboard:partners_dashboard')
        return super().get_login_redirect_url(request)
