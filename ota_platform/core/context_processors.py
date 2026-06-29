from .models import SiteSettings, Currency


def global_settings(request):
    """Global context processor for site settings"""
    try:
        site_settings = SiteSettings.objects.first()
    except SiteSettings.DoesNotExist:
        site_settings = None
    
    currencies = Currency.objects.filter(is_active=True)
    
    return {
        'site_settings': site_settings,
        'available_currencies': currencies,
    }