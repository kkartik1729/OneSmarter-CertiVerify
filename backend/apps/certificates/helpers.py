"""
Helper utilities for public certificate verification URLs and LinkedIn credentials.

LinkedIn strictly requires a publicly accessible HTTPS URL.
Localhost, 127.0.0.1, private LAN IPs, and non-HTTPS schemes are rejected by LinkedIn
with the message: "Please provide a valid URL."
"""
import re
from urllib.parse import quote, urlparse
from django.conf import settings

_PRIVATE_HOST_RE = re.compile(
    r"^(localhost|127\.\d+\.\d+\.\d+|0\.0\.0\.0|::1|10\.\d+\.\d+\.\d+|192\.168\.\d+\.\d+|172\.(1[6-9]|2\d|3[01])\.\d+\.\d+|.*\.local|.*\.internal|.*\.test)$",
    re.IGNORECASE,
)

_PLACEHOLDER_SUBSTRINGS = (
    "YOUR-DEPLOYED-DOMAIN",
    "YOUR_DEPLOYED_DOMAIN",
    "your-production-domain",
    "example.com",
    "placeholder",
)


def is_valid_public_https_url(url: str | None) -> bool:
    """
    Validates whether a URL is a production-grade, public HTTPS URL.
    Returns False for None, empty string, non-HTTPS, localhost, private LAN IPs,
    and unconfigured placeholder domains.
    """
    if not url or not isinstance(url, str):
        return False
    trimmed = url.strip()
    if not trimmed.lower().startswith("https://"):
        return False
    for placeholder in _PLACEHOLDER_SUBSTRINGS:
        if placeholder.lower() in trimmed.lower():
            return False
    try:
        parsed = urlparse(trimmed)
        hostname = (parsed.hostname or "").strip().lower()
        if not hostname:
            return False
        if _PRIVATE_HOST_RE.match(hostname):
            return False
        # Hostname should contain at least one dot (e.g. domain.tld)
        if "." not in hostname:
            return False
        return True
    except Exception:
        return False


def get_public_frontend_base_url() -> str | None:
    """
    Returns the configured, normalized public HTTPS frontend base URL,
    or None if no valid public HTTPS URL is configured.
    """
    # 1. Prefer PUBLIC_FRONTEND_URL setting
    pub = getattr(settings, "PUBLIC_FRONTEND_URL", None)
    if pub and is_valid_public_https_url(pub):
        return pub.strip().rstrip("/")

    # 2. Check FRONTEND_URL setting if it happens to be a valid public HTTPS URL
    fe = getattr(settings, "FRONTEND_URL", None)
    if fe and is_valid_public_https_url(fe):
        return fe.strip().rstrip("/")

    return None


def build_public_credential_url(certificate_number: str) -> tuple[str | None, bool]:
    """
    Builds the public credential URL for a certificate number.
    Returns (url, is_public_https).
    If no public HTTPS domain is configured, returns (None, False).
    """
    base = get_public_frontend_base_url()
    clean_num = (certificate_number or "").strip().upper()
    if not clean_num:
        return None, False
    if base:
        return f"{base}/verify-certificate/{quote(clean_num)}", True
    return None, False
