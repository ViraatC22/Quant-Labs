"""SSRF-hardened HTTP fetch for user-supplied URLs.

The vault URL importer fetches arbitrary links. Without guarding, a pasted or
malicious URL could make the server request loopback/LAN/metadata addresses
(e.g. the MinIO console, ``169.254.169.254``) and store the response. This
module resolves the host, rejects non-public IPs, and re-validates every
redirect hop before following it.

Note: this is not a defense against deliberate DNS-rebinding (a TOCTOU gap
exists between the resolve check and the socket connect). For a local-first
tool that is an acceptable trade-off and a large improvement over no guard.
"""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

MAX_REDIRECTS = 5


class SsrfError(ValueError):
    """Raised when a URL resolves to a disallowed (non-public) address."""


def _is_public_ip(ip_str: str) -> bool:
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        return False
    return not (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    )


def assert_public_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise SsrfError("URL must be an http(s) URL with a host.")

    try:
        infos = socket.getaddrinfo(parsed.hostname, parsed.port or None)
    except socket.gaierror as exc:
        raise SsrfError(f"Could not resolve host {parsed.hostname}.") from exc

    addresses = {str(info[4][0]) for info in infos}
    if not addresses:
        raise SsrfError(f"Host {parsed.hostname} did not resolve to any address.")
    for address in addresses:
        if not _is_public_ip(address):
            raise SsrfError(
                f"Refusing to fetch {parsed.hostname}: resolves to non-public address {address}."
            )


class _ValidatingRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[override]
        assert_public_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def safe_urlopen(
    url: str,
    *,
    timeout: float,
    headers: dict[str, str] | None = None,
):
    """Open ``url`` after SSRF validation, validating each redirect hop.

    Returns the response object (use as a context manager). Raises ``SsrfError``
    for disallowed targets.
    """
    assert_public_url(url)
    opener = build_opener(_ValidatingRedirectHandler())
    request = Request(url, headers=headers or {})
    return opener.open(request, timeout=timeout)
