from django.shortcuts import render
from .models import CarRental


def car_list(request):
    """Car rental listing view"""
    cars = CarRental.objects.filter(is_active=True, is_available=True)
    
    context = {
        'cars': cars,
    }
    
    return render(request, 'cars/car_list.html', context)