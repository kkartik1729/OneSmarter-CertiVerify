from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import UserProfile

User = get_user_model()


@receiver(post_save, sender=User)
def ensure_user_profile(sender, instance, created, **kwargs):
    """
    Ensure every User has an associated UserProfile.
    If the user has Django superuser or staff status, assign the ADMIN role.
    Standard registered users maintain the USER role.
    """
    is_admin_user = bool(instance.is_superuser or instance.is_staff)
    default_role = UserProfile.Role.ADMIN if is_admin_user else UserProfile.Role.USER

    profile, profile_created = UserProfile.objects.get_or_create(
        user=instance,
        defaults={"role": default_role},
    )

    # If the user is a superuser or staff, ensure the profile reflects ADMIN
    if is_admin_user and profile.role != UserProfile.Role.ADMIN:
        profile.role = UserProfile.Role.ADMIN
        profile.save(update_fields=["role", "updated_at"])
