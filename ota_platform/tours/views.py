from django.shortcuts import render
from .models import Tour


def tour_list(request):
    """Tour listing view"""
    tours = Tour.objects.filter(is_active=True, is_available=True)
    
    context = {
        'tours': tours,
    }
    
    return render(request, 'tours/tour_list.html', context)