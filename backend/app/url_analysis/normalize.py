"""URL parsing, validation and canonicalisation.

The same canonical form is used by the online analyser and by the offline
training pipeline (ml/url_classifier), so features are computed identically.
"""

from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass
from functools import lru_cache
from urllib.parse import urlsplit

import idna
import tldextract

MAX_URL_LENGTH = 4096

_SCHEME_RE = re.compile(r"^([a-zA-Z][a-zA-Z0-9+.\-]*):")
_FORBIDDEN_SCHEMES = {
    "javascript", "data", "file", "mailto", "ftp", "vbscript", "tel", "blob",
    "about", "chrome", "intent", "ws", "wss", "sms", "content", "smb",
}
_LABEL_RE = re.compile(r"^[a-z0-9_](?:[a-z0-9_\-]{0,61}[a-z0-9_])?$")
_CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]")

# Offline Public Suffix List snapshot bundled with tldextract: no network I/O.
_EXTRACT = tldextract.TLDExtract(suffix_list_urls=(), cache_dir=None)


class UrlValidationError(ValueError):
    """Raised for input that is not an analysable http(s) URL."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class ParsedUrl:
    original: str
    canonical: str  # canonical string used for features / dedup
    scheme: str
    host: str  # ASCII (punycode) lowercase host, no "www." stripping
    host_unicode: str  # human-readable host (IDN decoded when possible)
    port: int | None
    path: str
    query: str
    fragment: str
    userinfo: str | None
    is_ip: bool
    ip_obfuscated: bool  # decimal/hex/octal IPv4 notation
    had_scheme: bool
    registered_domain: str  # e.g. "example.co.uk"; host for IPs
    subdomain: str
    domain_label: str  # e.g. "example"
    suffix: str  # e.g. "co.uk"

    @property
    def host_no_www(self) -> str:
        return self.host[4:] if self.host.startswith("www.") else self.host


def _parse_obfuscated_ipv4(host: str) -> str | None:
    """Interpret inet_aton-style IPv4 forms (e.g. 2130706433, 0x7f.1, 0177.0.0.1)."""
    parts = host.split(".")
    if not 1 <= len(parts) <= 4 or any(p == "" for p in parts):
        return None
    nums: list[int] = []
    for p in parts:
        try:
            if p.lower().startswith("0x"):
                nums.append(int(p, 16))
            elif len(p) > 1 and p.startswith("0"):
                nums.append(int(p, 8))
            else:
                nums.append(int(p, 10))
        except ValueError:
            return None
    # inet_aton semantics: last part fills remaining bytes
    try:
        if len(nums) == 1:
            value = nums[0]
        elif len(nums) == 2:
            value = (nums[0] << 24) | nums[1]
            if nums[0] > 255 or nums[1] > 0xFFFFFF:
                return None
        elif len(nums) == 3:
            value = (nums[0] << 24) | (nums[1] << 16) | nums[2]
            if max(nums[:2]) > 255 or nums[2] > 0xFFFF:
                return None
        else:
            if max(nums) > 255:
                return None
            value = (nums[0] << 24) | (nums[1] << 16) | (nums[2] << 8) | nums[3]
        if not 0 <= value <= 0xFFFFFFFF:
            return None
        return str(ipaddress.IPv4Address(value))
    except (ValueError, ipaddress.AddressValueError):
        return None


@lru_cache(maxsize=8192)
def _to_ascii_host(host: str) -> tuple[str, str]:
    """Return (ascii_host, unicode_host). Raises UrlValidationError."""
    host = host.rstrip(".")
    if not host:
        raise UrlValidationError("invalid_host", "Empty host")
    try:
        if host.isascii():
            ascii_host = host.lower()
        else:
            ascii_host = idna.encode(host, uts46=True, transitional=False).decode("ascii")
    except idna.IDNAError:
        # Fall back to Python's IDNA 2003 codec (more permissive) before giving up.
        try:
            ascii_host = host.encode("idna").decode("ascii").lower()
        except UnicodeError as exc:
            raise UrlValidationError("invalid_host", "Host contains invalid characters") from exc
    try:
        unicode_host = idna.decode(ascii_host) if "xn--" in ascii_host else ascii_host
    except idna.IDNAError:
        unicode_host = ascii_host
    return ascii_host, unicode_host


def parse_url(raw: str, *, require_public_hostname: bool = True) -> ParsedUrl:
    """Validate and canonicalise user input into a ParsedUrl.

    Accepts inputs without a scheme ("example.com/login" -> http://...).
    Only http and https are allowed.
    """
    if not isinstance(raw, str):
        raise UrlValidationError("invalid_url", "URL must be a string")
    s = raw.strip()
    if not s:
        raise UrlValidationError("empty", "Empty input")
    if len(s) > MAX_URL_LENGTH:
        raise UrlValidationError("too_long", f"URL longer than {MAX_URL_LENGTH} characters")
    if _CONTROL_RE.search(s) or " " in s:
        raise UrlValidationError("invalid_url", "URL contains spaces or control characters")
    s = s.replace("\\", "/")  # browsers treat backslash as slash in http URLs

    had_scheme = True
    m = _SCHEME_RE.match(s)
    if m and s[m.end():].startswith("//"):
        scheme = m.group(1).lower()
    elif m and m.group(1).lower() in _FORBIDDEN_SCHEMES:
        raise UrlValidationError("unsupported_scheme", f"Scheme '{m.group(1).lower()}' is not supported")
    elif s.startswith("//"):
        scheme, s, had_scheme = "http", "http:" + s, False
    else:
        scheme, s, had_scheme = "http", "http://" + s, False
    if scheme not in ("http", "https"):
        raise UrlValidationError("unsupported_scheme", f"Scheme '{scheme}' is not supported")

    try:
        parts = urlsplit(s)
        port = parts.port
    except ValueError as exc:
        raise UrlValidationError("invalid_url", "Malformed URL (port or brackets)") from exc

    netloc = parts.netloc
    userinfo = netloc.rsplit("@", 1)[0] if "@" in netloc else None
    host_raw = parts.hostname or ""
    if not host_raw:
        raise UrlValidationError("invalid_host", "URL has no host")

    is_ip = False
    ip_obfuscated = False
    try:
        ip = ipaddress.ip_address(host_raw)
        is_ip = True
        host_ascii = host_unicode = ip.compressed
    except ValueError:
        decoded = _parse_obfuscated_ipv4(host_raw)
        if decoded is not None:
            is_ip = ip_obfuscated = True
            host_ascii = host_unicode = decoded
        else:
            host_ascii, host_unicode = _to_ascii_host(host_raw)
            if len(host_ascii) > 253:
                raise UrlValidationError("invalid_host", "Host name too long")
            labels = host_ascii.split(".")
            if any(not _LABEL_RE.match(lbl) for lbl in labels):
                raise UrlValidationError("invalid_host", "Host name contains invalid characters")
            if require_public_hostname and len(labels) < 2:
                raise UrlValidationError("invalid_host", "Host must be a public domain name")

    if is_ip:
        registered, sub, dom, suffix = host_ascii, "", host_ascii, ""
    else:
        ext = _EXTRACT(host_ascii)
        suffix = ext.suffix
        dom = ext.domain
        sub = ext.subdomain
        if require_public_hostname and not suffix:
            raise UrlValidationError("invalid_host", "Unknown top-level domain")
        registered = f"{dom}.{suffix}" if dom and suffix else host_ascii

    default_port = 80 if scheme == "http" else 443
    if port == default_port:
        port = None

    path = parts.path or ""
    if path == "/":
        path = ""
    host_for_canon = host_ascii[4:] if host_ascii.startswith("www.") else host_ascii
    if ":" in host_for_canon:  # IPv6
        host_for_canon = f"[{host_for_canon}]"
    canonical = host_for_canon + (f":{port}" if port else "") + path
    if parts.query:
        canonical += "?" + parts.query

    return ParsedUrl(
        original=raw,
        canonical=canonical,
        scheme=scheme,
        host=host_ascii,
        host_unicode=host_unicode,
        port=port,
        path=path,
        query=parts.query,
        fragment=parts.fragment,
        userinfo=userinfo,
        is_ip=is_ip,
        ip_obfuscated=ip_obfuscated,
        had_scheme=had_scheme,
        registered_domain=registered,
        subdomain=sub,
        domain_label=dom,
        suffix=suffix,
    )


def registered_domain_of(host: str) -> str:
    """Registered domain for an ASCII host (used for grouping and redirects)."""
    try:
        ipaddress.ip_address(host.strip("[]"))
        return host
    except ValueError:
        pass
    ext = _EXTRACT(host)
    return f"{ext.domain}.{ext.suffix}" if ext.domain and ext.suffix else host
