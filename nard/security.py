"""Pinned-TLS, GET-only HTTP transport. Redirects and browser execution are forbidden.

The security boundary ALSO requires Docker network isolation. No application-level
checker can guarantee that an arbitrary GET has no remote side effect (RFC 9110).
"""
from __future__ import annotations

import http.client
import ipaddress
import socket
import ssl
from dataclasses import dataclass
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

MAX_BYTES = 2_000_000
USER_AGENT = "narD-research-observer/0.1 (public-data; contact: configure-before-deployment)"
ALLOWED_TYPES = ("text/html", "text/plain", "application/xml", "text/xml", "application/rss+xml", "application/atom+xml", "application/json")


class FetchDenied(ValueError):
    pass


@dataclass(frozen=True)
class FetchResult:
    url: str
    status: int
    content_type: str
    body: bytes


def checked_url(url: str, allowed_host: str) -> tuple[str, str]:
    """Reject userinfo, redirects (at the caller), nonstandard ports and host confusion."""
    u = urlsplit(url)
    host = (u.hostname or "").rstrip(".").lower()
    if (u.scheme != "https" or not host or host != allowed_host.lower().rstrip(".")
            or u.username is not None or u.password is not None
            or u.port not in (None, 443) or u.fragment):
        raise FetchDenied("URL not covered by approved source host")
    if host.replace(".", "").isdigit():
        raise FetchDenied("IP-literal targets forbidden")
    try:
        ipaddress.ip_address(host.strip("[]"))
    except ValueError:
        pass
    else:
        raise FetchDenied("IP-literal targets forbidden")
    return host, (u.path or "/") + ("?" + u.query if u.query else "")


def public_addresses(host: str) -> list[str]:
    try:
        records = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    except OSError as exc:
        raise FetchDenied("DNS resolution failed") from exc
    ips = sorted({record[4][0] for record in records})
    # Fail closed if *any* answer is unsafe; do not silently fall back.
    if not ips or any(not ipaddress.ip_address(ip).is_global for ip in ips):
        raise FetchDenied("DNS returned non-public address")
    return ips


def pinned_get(url: str, allowed_host: str, max_bytes: int = MAX_BYTES) -> FetchResult:
    """Resolve once, connect to the validated IP, and verify TLS for original hostname."""
    host, path = checked_url(url, allowed_host)
    ip = public_addresses(host)[0]
    raw_socket = socket.create_connection((ip, 443), timeout=10)
    try:
        with ssl.create_default_context().wrap_socket(raw_socket, server_hostname=host) as tls:
            tls.settimeout(15)
            peer = tls.getpeername()[0]
            if peer != ip:
                raise FetchDenied("Connected peer differs from validated IP")
            # Origin-form path, not absolute-form URL; header values never from a page.
            request = (
                f"GET {path} HTTP/1.1\r\nHost: {host}\r\n"
                f"User-Agent: {USER_AGENT}\r\nAccept: text/html,application/xml,text/xml,application/json,text/plain;q=0.9\r\n"
                "Accept-Encoding: identity\r\nConnection: close\r\n\r\n"
            )
            tls.sendall(request.encode("ascii"))
            response = http.client.HTTPResponse(tls)
            response.begin()
            if 300 <= response.status < 400:
                raise FetchDenied("Redirect refused; new destinations require explicit review")
            if response.status != 200:
                raise FetchDenied(f"HTTP status {response.status}")
            length = response.getheader("Content-Length")
            if length and int(length) > max_bytes:
                raise FetchDenied("Response size limit exceeded")
            content_type = (response.getheader("Content-Type") or "").split(";", 1)[0].lower()
            if content_type not in ALLOWED_TYPES:
                raise FetchDenied("Unsupported content type")
            body = response.read(max_bytes + 1)
            if len(body) > max_bytes:
                raise FetchDenied("Response size limit exceeded")
            return FetchResult(url, response.status, content_type, body)
    finally:
        raw_socket.close()


def robots_allowed(url: str, allowed_host: str) -> bool:
    """Fail closed except for a genuine 404 robots response.

    Called separately to avoid applying a site-wide robots response to a different host.
    """
    host, _ = checked_url(url, allowed_host)
    robots_url = f"https://{host}/robots.txt"
    try:
        result = pinned_get(robots_url, host, max_bytes=200_000)
    except FetchDenied as exc:
        # Refusing 403, redirects, non-text responses etc. is intentional.
        if str(exc) == "HTTP status 404":
            return True
        return False
    parser = RobotFileParser()
    parser.parse(result.body.decode("utf-8", errors="replace").splitlines())
    return parser.can_fetch(USER_AGENT, url)
