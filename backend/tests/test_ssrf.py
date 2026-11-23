"""SSRF protection: address policy, DNS pinning/rebinding, unsafe redirects, limits."""

import http.server
import threading

import pytest

from app.net.safe_fetch import SafeFetcher, ip_block_reason


@pytest.mark.parametrize("ip", [
    "127.0.0.1", "10.1.2.3", "172.16.0.1", "192.168.1.1", "169.254.169.254", "100.64.0.1", "0.0.0.0",
    "224.0.0.1", "255.255.255.255", "::1", "fe80::1", "fc00::1", "::ffff:127.0.0.1", "::ffff:10.0.0.1",
    "64:ff9b::a00:1", "2002:7f00:1::", "198.18.0.1", "192.0.2.1",
])
def test_blocked_addresses(ip):
    assert ip_block_reason(ip) is not None


@pytest.mark.parametrize("ip", ["8.8.8.8", "1.1.1.1", "185.15.59.224", "2606:4700:4700::1111"])
def test_public_addresses_allowed(ip):
    assert ip_block_reason(ip) is None


def fetcher_with(resolver, **kw):
    return SafeFetcher(resolver=resolver, total_timeout=3, op_timeout=2, **kw)


def test_hostname_resolving_to_private_is_blocked():
    calls = []
    f = fetcher_with(lambda h, p: calls.append(h) or ["10.0.0.5"])
    r = f.fetch("http://intranet.example.com/")
    assert r.error_code == "blocked_address" and r.hops[0].blocked_reason == "private"
    assert calls == ["intranet.example.com"]


def test_any_private_answer_blocks_even_with_public_first():
    """Multi-answer DNS (public + private) must be rejected as a whole."""
    f = fetcher_with(lambda h, p: ["93.184.216.34", "127.0.0.1"])
    assert f.fetch("http://mixed.example.com/").error_code == "blocked_address"


def test_ip_literals_and_obfuscated_ip_blocked():
    f = fetcher_with(lambda h, p: pytest.fail("no DNS for IP literals"))
    assert f.fetch("http://169.254.169.254/latest/meta-data/").error_code == "blocked_address"
    assert f.fetch("http://2130706433/").error_code == "blocked_address"
    assert f.fetch("http://[::1]:80/").error_code == "blocked_address"


def test_only_http_and_https():
    f = fetcher_with(lambda h, p: ["8.8.8.8"])
    assert f.fetch("file:///etc/passwd").error_code == "unsupported_scheme"
    assert f.fetch("gopher://example.com/").error_code is not None


# ---------- local test server (allowed only through an explicit test policy) ----------
class Handler(http.server.BaseHTTPRequestHandler):
    routes: dict = {}

    def do_GET(self):  # noqa: N802
        status, headers, body = self.routes.get(self.path, (404, {}, b"nf"))
        self.send_response(status)
        for k, v in headers.items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


@pytest.fixture()
def server():
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield srv.server_address[1]
    srv.shutdown()


def local_policy(ip):
    """Test-only policy: treat 127.0.0.1 as 'public' (it is our test server), apply real rules otherwise."""
    return None if ip == "127.0.0.1" else ip_block_reason(ip)


def make(port, resolver=None, **kw):
    resolver = resolver or (lambda h, p: ["127.0.0.1"])
    return SafeFetcher(resolver=resolver, ip_policy=local_policy, allowed_ports={port}, total_timeout=3,
                       op_timeout=2, **kw)


def test_redirect_to_metadata_ip_is_blocked(server):
    Handler.routes = {"/start": (302, {"Location": "http://169.254.169.254/latest/meta-data/"}, b"")}
    r = make(server).fetch(f"http://app.test-site.com:{server}/start")
    assert r.hops[0].status == 302
    assert r.error_code == "blocked_address"
    assert r.hops[1].blocked_reason == "link_local"


def test_redirect_to_localhost_name_is_blocked(server):
    Handler.routes = {"/start": (301, {"Location": "http://localhost/admin"}, b"")}
    r = make(server).fetch(f"http://app.test-site.com:{server}/start")
    assert r.error_code.startswith("invalid_redirect_target")


def test_redirect_to_non_http_scheme_is_blocked(server):
    Handler.routes = {"/start": (302, {"Location": "file:///etc/passwd"}, b"")}
    r = make(server).fetch(f"http://app.test-site.com:{server}/start")
    assert r.error_code.startswith("invalid_redirect_target")


def test_every_hop_is_resolved_and_validated_again(server):
    """Second hop's hostname resolves to a private address -> stopped at that hop."""
    Handler.routes = {"/start": (302, {"Location": f"http://evil-rebind.com:{server}/x"}, b"")}

    def resolver(host, port):
        return ["127.0.0.1"] if host == "app.test-site.com" else ["192.168.0.10"]

    r = make(server, resolver).fetch(f"http://app.test-site.com:{server}/start")
    assert r.error_code == "blocked_address" and len(r.hops) == 2


def test_dns_resolved_once_per_hop_connection_pinned(server):
    """DNS rebinding defence: a second (different) DNS answer is never consulted for the same hop."""
    answers = iter([["127.0.0.1"], ["10.0.0.1"], ["10.0.0.1"]])
    calls = []

    def resolver(host, port):
        calls.append(host)
        return next(answers)

    Handler.routes = {"/ok": (200, {"Content-Type": "text/html"}, b"<html>ok</html>")}
    r = make(server, resolver).fetch(f"http://pinned.test-site.com:{server}/ok")
    assert r.error_code is None and r.final_status == 200
    assert calls == ["pinned.test-site.com"]  # exactly one resolution; connection went to the validated IP


def test_redirect_limit_and_loop(server):
    Handler.routes = {f"/r{i}": (302, {"Location": f"/r{i + 1}"}, b"") for i in range(10)}
    r = make(server, max_redirects=3).fetch(f"http://app.test-site.com:{server}/r0")
    assert r.error_code == "too_many_redirects" and len(r.hops) == 4
    Handler.routes = {"/a": (302, {"Location": "/b"}, b""), "/b": (302, {"Location": "/a"}, b"")}
    assert make(server).fetch(f"http://app.test-site.com:{server}/a").error_code == "redirect_loop"


def test_response_size_limit(server):
    Handler.routes = {"/big": (200, {"Content-Type": "text/html"}, b"a" * 300_000)}
    r = make(server).fetch(f"http://app.test-site.com:{server}/big", max_bytes=10_000)
    assert r.truncated and r.bytes_read == 10_000
    r2 = make(server).fetch(f"http://app.test-site.com:{server}/big", max_bytes=10_000, fail_if_larger=True)
    assert r2.error_code == "too_large"


def test_port_not_in_allow_list_is_not_contacted(server):
    f = SafeFetcher(resolver=lambda h, p: ["8.8.8.8"], allowed_ports={80, 443})
    r = f.fetch("http://example.com:6379/")
    assert r.error_code == "blocked_port"


def test_secret_query_values_masked_in_hops(server):
    Handler.routes = {"/ok?token=SECRET123&x=1": (200, {"Content-Type": "text/html"}, b"<html></html>")}
    r = make(server).fetch(f"http://app.test-site.com:{server}/ok?token=SECRET123&x=1")
    assert "SECRET123" not in r.hops[0].url
