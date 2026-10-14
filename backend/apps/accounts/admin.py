
from django.contrib import admin

from .models import MFARecoveryToken, PasswordResetRequest, PasswordResetToken, UserProfile


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "role",
        "organization",
        "created_at",
    )
    list_filter = ("role", "created_at")
    search_fields = (
        "user__username",
        "user__email",
        "organization",
    )
    readonly_fields = ("created_at", "updated_at")


@admin.register(MFARecoveryToken)
class MFARecoveryTokenAdmin(admin.ModelAdmin):
    list_display = ("user", "purpose", "is_used", "created_at", "expires_at")
    list_filter = ("is_used", "purpose", "created_at")
    search_fields = ("user__username", "user__email")
    readonly_fields = ("token_hash", "created_at", "expires_at", "used_at")


@admin.register(PasswordResetRequest)
class PasswordResetRequestAdmin(admin.ModelAdmin):
    list_display = ("user", "otp_verified", "is_completed", "attempts", "created_at", "otp_expires_at")
    list_filter = ("otp_verified", "is_completed", "created_at")
    search_fields = ("user__username", "user__email")
    readonly_fields = ("otp_hash", "reset_token_hash", "created_at", "otp_expires_at", "reset_token_expires_at")


@admin.register(PasswordResetToken)
class PasswordResetTokenAdmin(admin.ModelAdmin):
    list_display = ("user", "purpose", "is_used", "created_at", "expires_at")
    list_filter = ("is_used", "purpose", "created_at")
    search_fields = ("user__username", "user__email")
    readonly_fields = ("token_hash", "created_at", "expires_at", "used_at")

