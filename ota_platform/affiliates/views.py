from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse
from django.utils import timezone
from django.db.models import Sum, Count

from datetime import datetime, timedelta

from .models import (
    AffiliateProfile,
    AffiliatePromoCode,
    AffiliateResource,
    AffiliateClick,
)


def _get_affiliate_or_redirect(user):
    try:
        return user.affiliate_profile
    except Exception:
        return None


@login_required
def kyc_verification(request):
    """KYC verification process"""
    affiliate = _get_affiliate_or_redirect(request.user)
    if not affiliate:
        messages.error(request, 'You are not registered as an affiliate.')
        return redirect('home')

    if request.method == 'POST':
        affiliate.bank_name = request.POST.get('bank_name', affiliate.bank_name)
        affiliate.account_holder_name = request.POST.get('account_holder_name', affiliate.account_holder_name)
        affiliate.account_number = request.POST.get('account_number', affiliate.account_number)
        affiliate.routing_number = request.POST.get('routing_number', affiliate.routing_number)
        affiliate.swift_code = request.POST.get('swift_code', affiliate.swift_code)

        if 'id_document' in request.FILES:
            affiliate.id_document = request.FILES['id_document']
        if 'business_license' in request.FILES:
            affiliate.business_license = request.FILES['business_license']
        if 'tax_document' in request.FILES:
            affiliate.tax_document = request.FILES['tax_document']

        if getattr(affiliate, 'kyc_status', None) == 'pending':
            affiliate.kyc_status = 'under_review'
            affiliate.kyc_submitted_at = timezone.now()

        affiliate.save()
        messages.success(request, 'KYC information submitted successfully!')
        return redirect('affiliates:kyc_verification')

    return render(request, 'affiliates/kyc_verification.html', {'affiliate': affiliate})

@login_required
def affiliate_profile(request):
    affiliate = _get_affiliate_or_redirect(request.user)
    if not affiliate:
        messages.error(request, 'You are not registered as an affiliate.')
        return redirect('home')

    if request.method == 'POST':
        affiliate.company_name = request.POST.get('company_name', affiliate.company_name)
        affiliate.business_type = request.POST.get('business_type', affiliate.business_type)
        affiliate.business_phone = request.POST.get('business_phone', affiliate.business_phone)
        affiliate.business_email = request.POST.get('business_email', affiliate.business_email)
        affiliate.website = request.POST.get('website', affiliate.website)
        affiliate.social_media_links = request.POST.get('social_media_links', affiliate.social_media_links)
        follower_count = request.POST.get('follower_count')
        if follower_count.isdigit():
            affiliate.follower_count = int(follower_count)

        affiliate.save()
        messages.success(request, 'Profile updated successfully!')
        return redirect('affiliates:profile')

    return render(request, 'affiliates/profile.html', {'affiliate': affiliate})

@login_required
def promo_codes(request):
    affiliate = _get_affiliate_or_redirect(request.user)
    if not affiliate:
        messages.error(request, 'You are not registered as an affiliate.')
        return redirect('home')

    promo_codes_qs = affiliate.promo_codes.all().order_by('-created_at')
    return render(request, 'affiliates/promo_codes.html', {'affiliate': affiliate, 'promo_codes': promo_codes_qs})


@login_required
def create_promo_code(request):
    affiliate = _get_affiliate_or_redirect(request.user)
    if not affiliate:
        messages.error(request, 'You are not registered as an affiliate.')
        return redirect('home')

    if not getattr(affiliate, 'is_approved', False):
        messages.error(request, 'Your affiliate account must be approved to create promo codes.')
        return redirect('affiliates:dashboard')

    if request.method == 'POST':
        code_raw = request.POST.get('code', '')
        code = code_raw.strip().upper()
        description = request.POST.get('description', '')
        discount_type = request.POST.get('discount_type', '')
        service_type = request.POST.get('service_type', '')

        try:
            discount_value = float(request.POST.get('discount_value') or 0)
        except (TypeError, ValueError):
            discount_value = 0.0

        valid_from = None
        valid_until = None
        try:
            vf = request.POST.get('valid_from')
            if vf:
                valid_from = datetime.strptime(vf, '%Y-%m-%d')
            vu = request.POST.get('valid_until')
            if vu:
                valid_until = datetime.strptime(vu, '%Y-%m-%d')
        except ValueError:
            messages.error(request, 'Invalid date format for validity range.')
            return render(request, 'affiliates/create_promo_code.html', {'affiliate': affiliate})

        usage_limit = request.POST.get('usage_limit')
        min_amount = request.POST.get('min_amount')
        max_discount = request.POST.get('max_discount')

        if not code:
            messages.error(request, 'Promo code is required.')
            return render(request, 'affiliates/create_promo_code.html', {'affiliate': affiliate})

        if AffiliatePromoCode.objects.filter(code__iexact=code).exists():
            messages.error(request, 'This promo code already exists.')
            return render(request, 'affiliates/create_promo_code.html', {'affiliate': affiliate})

        promo_code = AffiliatePromoCode.objects.create(
            affiliate=affiliate,
            code=code,
            description=description,
            discount_type=discount_type,
            discount_value=discount_value,
            service_type=service_type,
            valid_from=valid_from,
            valid_until=valid_until,
            usage_limit=int(usage_limit) if usage_limit else None,
            min_amount=float(min_amount) if min_amount else None,
            max_discount=float(max_discount) if max_discount else None,
        )

        messages.success(request, f'Promo code "{promo_code.code}" created successfully!')
        return redirect('affiliates:promo_codes')

    return render(request, 'affiliates/create_promo_code.html', {'affiliate': affiliate})


@login_required
def earnings(request):
    affiliate = _get_affiliate_or_redirect(request.user)
    if not affiliate:
        messages.error(request, 'You are not registered as an affiliate.')
        return redirect('home')

    commissions = affiliate.commissions.all().order_by('-created_at')
    status = request.GET.get('status')
    if status:
        commissions = commissions.filter(status=status)

    payments = affiliate.payments.all().order_by('-payment_date')

    return render(request, 'affiliates/earnings.html', {
        'affiliate': affiliate,
        'commissions': commissions,
        'payments': payments,
        'selected_status': status,
    })


@login_required
def marketing_resources(request):
    affiliate = _get_affiliate_or_redirect(request.user)
    if not affiliate:
        messages.error(request, 'You are not registered as an affiliate.')
        return redirect('home')

    resources = AffiliateResource.objects.filter(is_active=True)
    resource_type = request.GET.get('type')
    if resource_type:
        resources = resources.filter(resource_type=resource_type)

    return render(request, 'affiliates/marketing_resources.html', {
        'affiliate': affiliate,
        'resources': resources,
        'selected_type': resource_type,
    })


@login_required
def dashboard(request):
    """Affiliate dashboard with basic stats"""
    affiliate = _get_affiliate_or_redirect(request.user)
    if not affiliate:
        messages.error(request, 'You are not registered as an affiliate.')
        return redirect('home')

    commissions_qs = affiliate.commissions.all()
    total_commissions = commissions_qs.aggregate(total=Sum('amount'))['total'] or 0
    pending_commissions = commissions_qs.filter(status='pending').count()
    approved_commissions = commissions_qs.filter(status='approved').count()
    recent_commissions = commissions_qs.order_by('-created_at')[:5]

    payments_total = affiliate.payments.aggregate(total=Sum('amount'))['total'] or 0

    promo_count = affiliate.promo_codes.count() if hasattr(affiliate, 'promo_codes') else 0

    context = {
        'affiliate': affiliate,
        'total_commissions': total_commissions,
        'pending_commissions': pending_commissions,
        'approved_commissions': approved_commissions,
        'recent_commissions': recent_commissions,
        'payments_total': payments_total,
        'promo_count': promo_count,
    }

    return render(request, 'affiliates/dashboard.html', context)


@login_required
def download_resource(request, resource_id):
    affiliate = _get_affiliate_or_redirect(request.user)
    if not affiliate:
        messages.error(request, 'You are not registered as an affiliate.')
        return redirect('home')

    resource = get_object_or_404(AffiliateResource, id=resource_id, is_active=True)
    resource.download_count = (resource.download_count or 0) + 1
    resource.save()

    if resource.download_file:
        data = resource.download_file.read()
        response = HttpResponse(data, content_type='application/octet-stream')
        response['Content-Disposition'] = f'attachment; filename="{resource.download_file.name}"'
        return response

    messages.error(request, 'Resource file not found.')
    return redirect('affiliates:marketing_resources')


def affiliate_signup(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        password = request.POST.get('password')
        company_name = request.POST.get('company_name')
        business_type = request.POST.get('business_type')
        website = request.POST.get('website')

        from django.contrib.auth import get_user_model, login
        User = get_user_model()

        if User.objects.filter(email=email).exists():
            messages.error(request, 'An account with this email already exists.')
            return render(request, 'affiliates/signup.html')

        user = User.objects.create_user(
            email=email,
            username=email,
            first_name=first_name,
            last_name=last_name,
            password=password
        )

        AffiliateProfile.objects.create(
            user=user,
            company_name=company_name,
            business_type=business_type,
            website=website,
            agreement_accepted=True,
            agreement_accepted_at=timezone.now()
        )

        login(request, user)
        messages.success(request, 'Affiliate account created successfully! Please complete your KYC verification.')
        return redirect('affiliates:kyc_verification')

    return render(request, 'affiliates/signup.html')


def affiliate_login(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        from django.contrib.auth import authenticate, login
        user = authenticate(request, username=email, password=password)

        if user is not None:
            if hasattr(user, 'affiliate_profile'):
                login(request, user)
                return redirect('affiliates:dashboard')
            messages.error(request, 'This account is not registered as an affiliate.')
        else:
            messages.error(request, 'Invalid email or password.')

    return render(request, 'affiliates/login.html')


@login_required
def referral_tracking(request):
    affiliate = _get_affiliate_or_redirect(request.user)
    if not affiliate:
        messages.error(request, 'You are not registered as an affiliate.')
        return redirect('home')

    referrals = affiliate.referrals.all().order_by('-referred_at')
    total_clicks = getattr(affiliate, 'clicks', []).count() if hasattr(affiliate, 'clicks') else 0
    converted_referrals = referrals.filter(converted=True).count()
    conversion_rate = (converted_referrals / total_clicks * 100) if total_clicks > 0 else 0

    today = timezone.now().date()
    monthly_referrals = []
    for i in range(6):
        start = (today.replace(day=1) - timedelta(days=30 * i)).replace(day=1)
        end = (start + timedelta(days=31)).replace(day=1)
        count = referrals.filter(referred_at__gte=start, referred_at__lt=end).count()
        monthly_referrals.append({'month': start.strftime('%b'), 'referrals': count})

    return render(request, 'affiliates/referral_tracking.html', {
        'affiliate': affiliate,
        'referrals': referrals,
        'total_clicks': total_clicks,
        'conversion_rate': conversion_rate,
        'monthly_referrals': monthly_referrals,
    })


def track_affiliate_click(request):
    affiliate_id = request.GET.get('aff_id')
    landing_page = request.GET.get('url', '/')

    if affiliate_id:
        affiliate = AffiliateProfile.objects.filter(affiliate_id=affiliate_id).first()
        if affiliate:
            AffiliateClick.objects.create(
                affiliate=affiliate,
                ip_address=request.META.get('REMOTE_ADDR') or '',
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
                referrer=request.META.get('HTTP_REFERER', ''),
                landing_page=landing_page,
            )
            request.session['affiliate_id'] = str(affiliate_id)

    return redirect(landing_page)