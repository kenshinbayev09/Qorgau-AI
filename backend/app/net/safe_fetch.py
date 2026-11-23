"""SSRF-hardened HTTP fetcher used for redirect-chain analysis and media download.

Guarantees
  * only http/https, only ports in `allowed_ports`;
  * every hostname is resolved once; *all* resolved addresses must be public
    (no loopback, private, link-local, CGNAT, multicast, reserved, NAT64/6to4/
    Teredo-embedded private IPv4, IPv4-mapped IPv6);
  * the TCP connection goes to the already-validated IP ("DNS pinning"), so a
    second, different DNS answer (DNS rebinding) cannot redirect the request;
    TLS still verifies the certificate against the original hostname (SNI);
  * every redirect hop is re-validated with the same rules;
  * hard limits: total deadline, per-operation socket timeout, max redirects,
    max response bytes; no cookies, no JavaScript, no form submission;
  * system proxy variables are ignored (http.client does not read them).
"""

from __future__ import annotations

import concurrent.futures
import http.client
import ipaddress
import re
import socket
import ssl
import time
from dataclasses import asdict, dataclass, field
from typing import BinaryIO, Callable, Iterable
from urllib.parse import urljoin

import certifi

from ..redaction import redact_url_for_client
from ..url_analysis.normalize import UrlValidationError, parse_url

USER_AGENT = "QorgauAI-LinkInspector/0.1 (educational; no JS; +https://example.invalid/qorgau)"
REDIRECT_CODES = {301, 302, 303, 307, 308}

_BLOCKED_NETS = [ipaddress.ip_network(n) for n in (
    "0.0.0.0/8", "10.0.0.0/8", "100.64.0.0/10", "127.0.0.0/8", "169.254.0.0/16", "172.16.0.0/12",
    "192.0.0.0/24", "192.0.2.0/24", "192.88.99.0/24", "192.168.0.0/16", "198.18.0.0/15",
    "198.51.100.0/24", "203.0.113.0/24", "224.0.0.0/4", "240.0.0.0/4", "255.255.255.255/32",
    "::/128", "::1/128", "::ffff:0:0/96", "64:ff9b::/96", "64:ff9b:1::/48", "100::/64", "2001::/23",
    "2001:db8::/32", "2002::/16", "fc00::/7", "fe80::/10", "fec0::/10", "ff00::/8",
)]


class SafeFetchError(Exception):
    def __init__(self, code: str, message: str = ""):
        super().__init__(message or code)
        self.code = code


def ip_block_reason(ip_str: str) -> str | None:
    """Return why an address is not allowed, or None when it is a public unicast address."""
    try:
        ip = ipaddress.ip_address(ip_str.split("%")[0])
    except ValueError:
        return "unparsable_ip"
    if isinstance(ip, ipaddress.IPv6Address):
        embedded = ip.ipv4_mapped or (ip.sixtofour if ip.sixtofour else None)
        if ip.teredo:
            embedded = ip.teredo[1]
        if embedded is not None:
            inner = ip_block_reason(str(embedded))
            if inner:
                return f"embedded_ipv4_{inner}"
    for net in _BLOCKED_NETS:
        if ip.version == net.version and ip in net:
            if ip.is_loopback:
                return "loopback"
            if ip.is_link_local:
                return "link_local"
            if ip.is_multicast:
                return "multicast"
            if ip.is_private:
                return "private"
            return "reserved"
    if not ip.is_global:
        return "not_global"
    return None


Resolver = Callable[[str, int], list[str]]


def system_resolver(timeout: float) -> Resolver:
    pool = concurrent.futures.ThreadPoolExecutor(max_workers=4, thread_name_prefix="dns")

    def resolve(host: str, port: int) -> list[str]:
        fut = pool.submit(socket.getaddrinfo, host, port, 0, socket.SOCK_STREAM)
        try:
            infos = fut.result(timeout=timeout)
        except concurrent.futures.TimeoutError as exc:
            raise SafeFetchError("dns_timeout") from exc
        except socket.gaierror as exc:
            raise SafeFetchError("dns_failed", str(exc)) from exc
        return list(dict.fromkeys(info[4][0] for info in infos))

    return resolve


@dataclass
class Hop:
    url: str  # client-safe (secrets masked)
    host: str
    ip: str | None = None
    status: int | None = None
    location: str | None = None
    blocked_reason: str | None = None
    elapsed_ms: int = 0


@dataclass
class FetchResult:
    hops: list[Hop] = field(default_factory=list)
    final_url: str | None = None  # client-safe
    final_host: str | None = None
    final_status: int | None = None
    content_type: str | None = None
    bytes_read: int = 0
    truncated: bool = False
    body_head: bytes = b""  # first bytes (for HTML signals / magic-byte checks)
    error_code: str | None = None

    def to_dict(self) -> dict:
        d = asdict(self)
        d.pop("body_head")
        return d


def _absolute(p) -> str:
    host = f"[{p.host}]" if ":" in p.host else p.host
    port = f":{p.port}" if p.port else ""
    query = f"?{p.query}" if p.query else ""
    return f"{p.scheme}://{host}{port}{p.path or '/'}{query}"


class _PinnedHTTPConnection(http.client.HTTPConnection):
    def __init__(self, host: str, ip: str, port: int, timeout: float):
        super().__init__(host, port, timeout=timeout)
        self._pinned_ip = ip

    def connect(self) -> None:
        self.sock = socket.create_connection((self._pinned_ip, self.port), self.timeout)


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, host: str, ip: str, port: int, timeout: float, context: ssl.SSLContext):
        super().__init__(host, port, timeout=timeout, context=context)
        self._pinned_ip = ip
        self._ctx = context

    def connect(self) -> None:
        raw = socket.create_connection((self._pinned_ip, self.port), self.timeout)
        try:
            self.sock = self._ctx.wrap_socket(raw, server_hostname=self.host)
        except Exception:
            raw.close()
            raise


class SafeFetcher:
    def __init__(
        self,
        *,
        total_timeout: float = 8.0,
        op_timeout: float = 4.0,
        max_redirects: int = 5,
        allowed_ports: Iterable[int] = (80, 443, 8080, 8443),
        resolver: Resolver | None = None,
        ip_policy: Callable[[str], str | None] = ip_block_reason,
        ssl_context: ssl.SSLContext | None = None,
    ):
        self.total_timeout = total_timeout
        self.op_timeout = op_timeout
        self.max_redirects = max_redirects
        self.allowed_ports = set(allowed_ports)
        self.resolver = resolver or system_resolver(op_timeout)
        self.ip_policy = ip_policy
        # certifi's Mozilla CA bundle: consistent trust store across Windows/Linux/macOS hosts
        self.ssl_context = ssl_context or ssl.create_default_context(cafile=certifi.where())

    def fetch(
        self,
        url: str,
        *,
        max_bytes: int = 256 * 1024,
        sink: BinaryIO | None = None,
        fail_if_larger: bool = False,
        head_bytes: int = 64 * 1024,
        accept: str = "text/html,application/xhtml+xml;q=0.9,*/*;q=0.1",
    ) -> FetchResult:
        """Follow redirects safely. Never raises for network problems: sets error_code."""
        result = FetchResult()
        deadline = time.monotonic() + self.total_timeout
        current = url
        seen: set[str] = set()
        for hop_no in range(self.max_redirects + 1):
            try:
                p = parse_url(current)
            except UrlValidationError as exc:
                result.error_code = f"invalid_redirect_target:{exc.code}" if hop_no else exc.code
                return result
            hop = Hop(url=redact_url_for_client(_absolute(p)), host=p.host_unicode)
            result.hops.append(hop)
            key = f"{p.scheme}://{p.host}:{p.port}{p.path}?{p.query}"
            if key in seen:
                result.error_code = "redirect_loop"
                return result
            seen.add(key)
            port = p.port or (443 if p.scheme == "https" else 80)

            t0 = time.monotonic()
            try:
                if p.is_ip:
                    ips = [p.host]
                else:
                    ips = self.resolver(p.host, port)
                if not ips:
                    raise SafeFetchError("dns_failed")
                # Validate EVERY address before connecting to any of them.
                for ip in ips:
                    reason = self.ip_policy(ip)
                    if reason:
                        hop.ip = ip
                        hop.blocked_reason = reason
                        result.error_code = "blocked_address"
                        return result
                if port not in self.allowed_ports:
                    hop.blocked_reason = f"port_{port}_not_allowed"
                    result.error_code = "blocked_port"
                    return result
                # Prefer IPv4 (IPv6 is often unroutable on mobile/home networks); try at most 2 addresses.
                candidates = sorted(ips, key=lambda a: ":" in a)[:2]
                for n, ip in enumerate(candidates):
                    hop.ip = ip
                    if deadline - time.monotonic() <= 0:
                        raise SafeFetchError("timeout")
                    try:
                        status, location, ctype, done = self._request(
                            p, ip, port, deadline, max_bytes, sink, fail_if_larger, head_bytes, accept, result)
                        break
                    except (socket.timeout, TimeoutError, ConnectionError, OSError):
                        if n + 1 >= len(candidates) or result.bytes_read:
                            raise
            except SafeFetchError as exc:
                result.error_code = exc.code
                hop.elapsed_ms = int((time.monotonic() - t0) * 1000)
                return result
            except ssl.SSLCertVerificationError:
                result.error_code = "tls_certificate_invalid"
                return result
            except ssl.SSLError:
                result.error_code = "tls_error"
                return result
            except (socket.timeout, TimeoutError):
                result.error_code = "timeout"
                return result
            except (ConnectionError, OSError, http.client.HTTPException):
                result.error_code = "connection_failed"
                return result
            hop.elapsed_ms = int((time.monotonic() - t0) * 1000)
            hop.status = status
            if status in REDIRECT_CODES and location:
                nxt = urljoin(_absolute(p), location.strip())
                hop.location = redact_url_for_client(nxt)
                current = nxt
                continue
            result.final_url = hop.url
            result.final_host = p.host_unicode
            result.final_status = status
            result.content_type = ctype
            return result
        result.error_code = "too_many_redirects"
        return result

    def _request(self, p, ip, port, deadline, max_bytes, sink, fail_if_larger, head_bytes, accept, result):
        timeout = max(0.5, min(self.op_timeout, deadline - time.monotonic()))
        if p.scheme == "https":
            conn = _PinnedHTTPSConnection(p.host, ip, port, timeout, self.ssl_context)
        else:
            conn = _PinnedHTTPConnection(p.host, ip, port, timeout)
        try:
            target = (p.path or "/") + (f"?{p.query}" if p.query else "")
            conn.request("GET", target, headers={
                "User-Agent": USER_AGENT, "Accept": accept, "Accept-Encoding": "identity",
                "Connection": "close",
            })
            resp = conn.getresponse()
            status = resp.status
            location = resp.getheader("Location")
            ctype = (resp.getheader("Content-Type") or "").split(";")[0].strip().lower() or None
            if status in REDIRECT_CODES:
                return status, location, ctype, True
            declared = resp.getheader("Content-Length")
            if fail_if_larger and declared and declared.isdigit() and int(declared) > max_bytes:
                raise SafeFetchError("too_large")
            result.body_head = b""
            result.bytes_read = 0
            while True:
                if time.monotonic() > deadline:
                    raise SafeFetchError("timeout")
                chunk = resp.read(min(64 * 1024, max_bytes + 1 - result.bytes_read))
                if not chunk:
                    break
                result.bytes_read += len(chunk)
                if len(result.body_head) < head_bytes:
                    result.body_head += chunk[: head_bytes - len(result.body_head)]
                if result.bytes_read > max_bytes:
                    if fail_if_larger:
                        raise SafeFetchError("too_large")
                    result.truncated = True
                    result.bytes_read = max_bytes
                    break
                if sink is not None:
                    sink.write(chunk)
            return status, location, ctype, True
        finally:
            conn.close()


_META_REFRESH = re.compile(rb"<meta[^>]+http-equiv\s*=\s*[\"']?refresh[\"']?[^>]*content\s*=\s*[\"']?\s*\d+\s*;\s*url\s*=\s*([^\"'>\s]+)", re.I)
_PASSWORD_INPUT = re.compile(rb"<input[^>]+type\s*=\s*[\"']?password", re.I)
_FORM_ACTION = re.compile(rb"<form[^>]+action\s*=\s*[\"']?(https?://[^\"'>\s]+)", re.I)


def html_signals(body_head: bytes) -> dict:
    """Pattern-match a page *as untrusted data*. Nothing here is executed or followed."""
    out: dict = {}
    m = _META_REFRESH.search(body_head)
    if m:
        out["meta_refresh_target"] = m.group(1)[:200].decode("ascii", "replace")
    out["password_field"] = bool(_PASSWORD_INPUT.search(body_head))
    forms = [f.decode("ascii", "replace")[:200] for f in _FORM_ACTION.findall(body_head)[:5]]
    if forms:
        out["external_form_actions"] = forms
    return out
