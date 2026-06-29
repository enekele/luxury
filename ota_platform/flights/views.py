from django.shortcuts import render
from .models import Flight


def flight_list(request):
    """Flight listing view"""
    flights = Flight.objects.filter(is_active=True).order_by('departure_time')
    
    context = {
        'flights': flights,
    }
    
    return render(request, 'flights/flight_list.html', context)


def flight_search(request):
    """Flight search view"""
    return render(request, 'flights/flight_list.html')