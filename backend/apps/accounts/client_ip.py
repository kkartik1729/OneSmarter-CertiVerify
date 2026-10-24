"""Client address resolution that trusts only explicitly configured proxies."""

import ipaddress
import logging

from django.conf import settings

logger = logging.getLogger(__name__)


def get_client_ip(request):
    remote = request.META.get("REMOTE_ADDR") or ""
    try:
        peer = ipaddress.ip_address(remote)
    except ValueError:
        return None

    trusted_networks = []
    for value in getattr(settings, "TRUSTED_PROXY_IPS", ()):
        try:
            trusted_networks.append(ipaddress.ip_network(value, strict=False))
        except ValueError:
            logger.error("Ignoring invalid trusted proxy network configuration")

    def is_trusted(address):
        return any(address in network for network in trusted_networks)

    if not is_trusted(peer):
        return str(peer)

    candidates = []
    for value in request.META.get("HTTP_X_FORWARDED_FOR", "").split(","):
        try:
            candidates.append(ipaddress.ip_address(value.strip()))
        except ValueError:
            continue
    for address in reversed(candidates):
        if not is_trusted(peer):
            break
        peer = address
    return str(peer)
