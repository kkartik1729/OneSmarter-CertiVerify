
from .models import AuditLog


def log_action(
    *,
    action,
    actor=None,
    target_type="",
    target_id="",
    description="",
    metadata=None,
    ip_address=None,
):
    """
    Create an audit record.

    Never pass passwords, JWTs, MFA codes, or other secrets
    through description or metadata.
    """
    if actor is not None and not getattr(actor, "is_authenticated", False):
        actor = None

    return AuditLog.objects.create(
        actor=actor,
        action=action,
        target_type=str(target_type)[:100],
        target_id=str(target_id)[:100],
        description=description,
        metadata=metadata or {},
        ip_address=ip_address,
    )
