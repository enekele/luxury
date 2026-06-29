from rest_framework.throttling import UserRateThrottle, AnonRateThrottle


class BurstRateThrottle(UserRateThrottle):
    """
    High frequency throttling for authenticated users
    """
    scope = 'burst'


class SustainedRateThrottle(UserRateThrottle):
    """
    Lower frequency throttling for sustained usage
    """
    scope = 'sustained'


class LoginRateThrottle(AnonRateThrottle):
    """
    Throttling for login attempts
    """
    scope = 'login'


class SearchRateThrottle(AnonRateThrottle):
    """
    Throttling for search requests
    """
    scope = 'search'


class BookingRateThrottle(UserRateThrottle):
    """
    Throttling for booking creation
    """
    scope = 'booking'