from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.http import HttpResponseForbidden
from django.urls import reverse


def partner_required(view_func):
    """Allow only authenticated users with an active Partner profile."""

    @wraps(view_func)
    def wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(
                request.get_full_path(),
                login_url=reverse('account_login'),
            )

        partner = getattr(request.user, 'partner_profile', None)
        if partner is None or not partner.is_active:
            return HttpResponseForbidden(
                'An active partner account is required to access this page.'
            )

        request.partner = partner
        return view_func(request, *args, **kwargs)

    return wrapped_view
