"""Rate limits keyed by trusted network identity, never arbitrary proxy headers."""

import hashlib

from rest_framework.throttling import SimpleRateThrottle
from .client_ip import get_client_ip


class TrustedIPRateThrottle(SimpleRateThrottle):
    def get_cache_key(self, request, view):
        address = get_client_ip(request) or "unknown"
        return self.cache_format % {"scope": self.scope, "ident": address}


class EmailVerificationIPThrottle(TrustedIPRateThrottle):
    scope = "email_verification_ip"


class PasswordResetIPThrottle(TrustedIPRateThrottle):
    scope = "password_reset_ip"


class LoginIPThrottle(TrustedIPRateThrottle):
    scope = "login_ip"


class LoginIdentityThrottle(SimpleRateThrottle):
    """Limit repeated attempts for one normalized login identifier."""

    scope = "login_identity"

    def get_cache_key(self, request, view):
        identity = str(request.data.get("username", "")).strip().casefold()
        if not identity:
            identity = str(request.data.get("email", "")).strip().casefold()
        if not identity:
            return None
        # Hash identifiers so cache keys do not contain email addresses or usernames.
        digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()
        return self.cache_format % {"scope": self.scope, "ident": digest}


class PublicVerificationIPThrottle(TrustedIPRateThrottle):
    scope = "public_verification_ip"
