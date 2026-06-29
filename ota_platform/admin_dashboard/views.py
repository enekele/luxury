from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.db.models import Sum, Count, Avg
from django.utils import timezone
from datetime import datetime, timedelta
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.db import models

from .models import AdminActivity, SystemSettings, RevenueReport, PartnerCommission
from users.models import User
from hotels.models import Hotel
from flights.models import Flight
from cars.models import CarRental
from tours.models import Tour
from bookings.models import Booking
from reviews.models import Review
from core.models import Promotion


@staff_member_required
def dashboard(request):
    """Main admin dashboard"""
    # Get date ranges
    today = timezone.now().date()
    last_30_days = today - timedelta(days=30)
    last_7_days = today - timedelta(days=7)
    
    # Basic statistics
    total_users = User.objects.count()
    new_users_30d = User.objects.filter(date_joined__gte=last_30_days).count()
    total_bookings = Booking.objects.count()
    pending_bookings = Booking.objects.filter(status='pending').count()
    
    # Revenue statistics
    total_revenue = Booking.objects.filter(
        status='confirmed'
    ).aggregate(total=Sum('total_amount'))['total'] or 0
    
    revenue_30d = Booking.objects.filter(
        status='confirmed',
        created_at__gte=last_30_days
    ).aggregate(total=Sum('total_amount'))['total'] or 0
    
    # Service statistics
    hotel_bookings = Booking.objects.filter(content_type__model='hotel').count()
    flight_bookings = Booking.objects.filter(content_type__model='flight').count()
    car_bookings = Booking.objects.filter(content_type__model='carrental').count()
    tour_bookings = Booking.objects.filter(content_type__model='tour').count()
    
    # Recent activities
    recent_bookings = Booking.objects.order_by('-created_at')[:10]
    recent_users = User.objects.order_by('-date_joined')[:10]
    recent_reviews = Review.objects.filter(is_approved=True).order_by('-created_at')[:5]
    
    # Chart data for revenue
    revenue_chart_data = []
    for i in range(30):
        date = today - timedelta(days=i)
        daily_revenue = Booking.objects.filter(
            status='confirmed',
            created_at__date=date
        ).aggregate(total=Sum('total_amount'))['total'] or 0
        revenue_chart_data.append({
            'date': date.strftime('%Y-%m-%d'),
            'revenue': float(daily_revenue)
        })
    
    context = {
        'total_users': total_users,
        'new_users_30d': new_users_30d,
        'total_bookings': total_bookings,
        'pending_bookings': pending_bookings,
        'total_revenue': total_revenue,
        'revenue_30d': revenue_30d,
        'hotel_bookings': hotel_bookings,
        'flight_bookings': flight_bookings,
        'car_bookings': car_bookings,
        'tour_bookings': tour_bookings,
        'recent_bookings': recent_bookings,
        'recent_users': recent_users,
        'recent_reviews': recent_reviews,
        'revenue_chart_data': revenue_chart_data,
    }
    
    return render(request, 'admin_dashboard/dashboard.html', context)


@staff_member_required
def users_management(request):
    """User management page"""
    users = User.objects.all().order_by('-date_joined')
    
    # Filters
    search = request.GET.get('search')
    status = request.GET.get('status')
    
    if search:
        users = users.filter(
            models.Q(first_name__icontains=search) |
            models.Q(last_name__icontains=search) |
            models.Q(email__icontains=search)
        )
    
    if status == 'premium':
        users = users.filter(is_premium=True)
    elif status == 'verified':
        users = users.filter(is_verified=True)
    elif status == 'active':
        users = users.filter(is_active=True)
    
    paginator = Paginator(users, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'users': page_obj,
        'search': search,
        'status': status,
    }
    
    return render(request, 'admin_dashboard/users_management.html', context)


@staff_member_required
def bookings_management(request):
    """Booking management page"""
    bookings = Booking.objects.all().order_by('-created_at')
    
    # Filters
    status = request.GET.get('status')
    service_type = request.GET.get('service_type')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    
    if status:
        bookings = bookings.filter(status=status)
    
    if service_type:
        bookings = bookings.filter(content_type__model=service_type)
    
    if date_from:
        bookings = bookings.filter(created_at__date__gte=date_from)
    
    if date_to:
        bookings = bookings.filter(created_at__date__lte=date_to)
    
    paginator = Paginator(bookings, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'bookings': page_obj,
        'status': status,
        'service_type': service_type,
        'date_from': date_from,
        'date_to': date_to,
    }
    
    return render(request, 'admin_dashboard/bookings_management.html', context)


@staff_member_required
def content_management(request):
    """Content management page"""
    hotels_count = Hotel.objects.count()
    flights_count = Flight.objects.count()
    cars_count = CarRental.objects.count()
    tours_count = Tour.objects.count()
    
    # Recent content
    recent_hotels = Hotel.objects.order_by('-created_at')[:5]
    recent_tours = Tour.objects.order_by('-created_at')[:5]
    
    # Pending reviews
    pending_reviews = Review.objects.filter(is_approved=False).count()
    
    context = {
        'hotels_count': hotels_count,
        'flights_count': flights_count,
        'cars_count': cars_count,
        'tours_count': tours_count,
        'recent_hotels': recent_hotels,
        'recent_tours': recent_tours,
        'pending_reviews': pending_reviews,
    }
    
    return render(request, 'admin_dashboard/content_management.html', context)


@staff_member_required
def analytics(request):
    """Analytics and reports page"""
    # Revenue analytics
    today = timezone.now().date()
    last_30_days = today - timedelta(days=30)
    
    # Monthly revenue by service type
    monthly_revenue = {}
    for service in ['hotel', 'flight', 'carrental', 'tour']:
        revenue = Booking.objects.filter(
            content_type__model=service,
            status='confirmed',
            created_at__gte=last_30_days
        ).aggregate(total=Sum('total_amount'))['total'] or 0
        monthly_revenue[service] = float(revenue)
    
    # User growth
    user_growth = []
    for i in range(12):
        month_start = today.replace(day=1) - timedelta(days=30*i)
        month_end = month_start + timedelta(days=30)
        users_count = User.objects.filter(
            date_joined__gte=month_start,
            date_joined__lt=month_end
        ).count()
        user_growth.append({
            'month': month_start.strftime('%b %Y'),
            'users': users_count
        })
    
    # Top destinations
    top_destinations = Booking.objects.values(
        'hotel__city__name', 'hotel__city__country__name'
    ).annotate(
        booking_count=Count('id')
    ).order_by('-booking_count')[:10]
    
    context = {
        'monthly_revenue': monthly_revenue,
        'user_growth': user_growth,
        'top_destinations': top_destinations,
    }
    
    return render(request, 'admin_dashboard/analytics.html', context)


@staff_member_required
def promotions_management(request):
    """Promotions management page"""
    promotions = Promotion.objects.all().order_by('-created_at')
    
    context = {
        'promotions': promotions,
    }
    
    return render(request, 'admin_dashboard/promotions_management.html', context)


@staff_member_required
def system_settings(request):
    """System settings page"""
    settings, created = SystemSettings.objects.get_or_create(id=1)
    
    if request.method == 'POST':
        settings.maintenance_mode = request.POST.get('maintenance_mode') == 'on'
        settings.maintenance_message = request.POST.get('maintenance_message', '')
        settings.max_booking_days_advance = int(request.POST.get('max_booking_days_advance', 365))
        settings.min_booking_hours_advance = int(request.POST.get('min_booking_hours_advance', 2))
        settings.auto_confirm_bookings = request.POST.get('auto_confirm_bookings') == 'on'
        settings.email_notifications_enabled = request.POST.get('email_notifications_enabled') == 'on'
        settings.sms_notifications_enabled = request.POST.get('sms_notifications_enabled') == 'on'
        settings.save()
        
        messages.success(request, 'System settings updated successfully!')
        return redirect('admin_dashboard:system_settings')
    
    context = {
        'settings': settings,
    }
    
    return render(request, 'admin_dashboard/system_settings.html', context)