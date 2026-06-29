from rest_framework.authentication import TokenAuthentication
from rest_framework.authtoken.models import Token
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from rest_framework import exceptions

User = get_user_model()


class CustomTokenAuthentication(TokenAuthentication):
    """
    Custom token authentication that includes user verification check
    """
    
    def authenticate_credentials(self, key):
        model = self.get_model()
        try:
            token = model.objects.select_related('user').get(key=key)
        except model.DoesNotExist:
            raise exceptions.AuthenticationFailed(_('Invalid token.'))

        if not token.user.is_active:
            raise exceptions.AuthenticationFailed(_('User inactive or deleted.'))

        # Optional: Check if user is verified for certain endpoints
        # if not token.user.is_verified:
        #     raise exceptions.AuthenticationFailed(_('User not verified.'))

        return (token.user, token)


class APIKeyAuthentication(TokenAuthentication):
    """
    API Key authentication for partner integrations
    """
    keyword = 'ApiKey'
    model = Token
    
    def authenticate_credentials(self, key):
        model = self.get_model()
        try:
            token = model.objects.select_related('user').get(key=key)
        except model.DoesNotExist:
            raise exceptions.AuthenticationFailed(_('Invalid API key.'))

        if not token.user.is_active:
            raise exceptions.AuthenticationFailed(_('API key inactive.'))

        if not token.user.is_staff:
            raise exceptions.AuthenticationFailed(_('API key not authorized.'))

        return (token.user, token)