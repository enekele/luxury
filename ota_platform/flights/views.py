from django.shortcuts import render
from django.utils import timezone

from .models import Flight


def flight_list(request):
    """Flight listing view"""
    flights = Flight.objects.filter(
        is_active=True,
        status='scheduled',
        available_seats__gt=0,
        departure_time__gt=timezone.now(),
    ).order_by('departure_time')
    
    context = {
        'flights': flights,
    }
    
    return render(request, 'flights/flight_list.html', context)


def flight_search(request):
    """Flight search view"""
    return render(request, 'flights/flight_list.html')
