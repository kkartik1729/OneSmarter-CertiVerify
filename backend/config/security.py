"""Small dependency-free security configuration validators."""


_INSECURE_SECRET_KEYS = {
    "dev-only-change-this-key-before-deployment",
    "replace-with-a-secure-django-secret-key",
    "change-me",
    "changeme",
    "secret",
}


def validate_django_secret_key(value):
    key = (value or "").strip()
    folded = key.casefold()
    if (
        not key
        or folded in _INSECURE_SECRET_KEYS
        or any(marker in folded for marker in ("replace-with", "your-secret", "change-me", "dev-only"))
    ):
        raise ValueError(
            "DJANGO_SECRET_KEY must be set to a unique, securely generated secret."
        )
    return key
