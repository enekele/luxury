from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth import get_user_model
from .models import UserProfile, UserActivity, WishlistItem, User

User = get_user_model()


class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'Profile'


class UserAdmin(BaseUserAdmin):
    inlines = (UserProfileInline,)
    list_display = ('email', 'first_name', 'last_name', 'is_verified', 'is_premium', 'total_bookings', 'loyalty_points')
    list_filter = ('is_verified', 'is_premium', 'preferred_currency', 'country')
    search_fields = ('email', 'first_name', 'last_name')
    ordering = ('email',)
    
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Personal Info', {'fields': ('phone', 'date_of_birth', 'country', 'city', 'address', 'profile_picture')}),
        ('Preferences', {'fields': ('preferred_currency', 'preferred_language')}),
        ('Verification', {'fields': ('is_verified', 'is_premium', 'premium_expires')}),
        ('Referrals', {'fields': ('referral_code', 'referred_by')}),
        ('Statistics', {'fields': ('total_bookings', 'total_spent', 'loyalty_points')}),
        ('Notifications', {'fields': ('email_notifications', 'sms_notifications', 'promotional_emails')}),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'first_name', 'last_name', 'password1', 'password2'),
        }),
    )


try:
    admin.site.unregister(User)
except admin.sites.NotRegistered:
    pass  # User model was not registered, so ignore

admin.site.register(User, UserAdmin)


@admin.register(UserActivity)
class UserActivityAdmin(admin.ModelAdmin):
    list_display = ('user', 'activity_type', 'description', 'timestamp')
    list_filter = ('activity_type', 'timestamp')
    search_fields = ('user__email', 'activity_type', 'description')
    readonly_fields = ('timestamp',)


@admin.register(WishlistItem)
class WishlistItemAdmin(admin.ModelAdmin):
    list_display = ('user', 'content_type', 'object_id', 'created_at')
    list_filter = ('content_type', 'created_at')
    search_fields = ('user__email',)