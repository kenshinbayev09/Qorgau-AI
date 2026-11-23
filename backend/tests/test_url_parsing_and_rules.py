import pytest

from app.url_analysis.brand import analyse_brand
from app.url_analysis.features import FEATURE_NAMES, extract_features
from app.url_analysis.heuristics import lexical_signals, rule_score
from app.url_analysis.normalize import UrlValidationError, parse_url


def ids(url):
    return {s.id for s in lexical_signals(parse_url(url))}


# ---------- valid / invalid input ----------
@pytest.mark.parametrize("raw,host,scheme", [
    ("https://Example.COM/path?a=1", "example.com", "https"),
    ("example.com", "example.com", "http"),
    ("  www.kaspi.kz/shop  ", "www.kaspi.kz", "http"),
    ("//cdn.example.org/x", "cdn.example.org", "http"),
    ("http://[2001:4860:4860::8888]/", "2001:4860:4860::8888", "http"),
    ("https://xn--80ak6aa92e.com", "xn--80ak6aa92e.com", "https"),
])
def test_valid_urls(raw, host, scheme):
    p = parse_url(raw)
    assert p.host == host and p.scheme == scheme


@pytest.mark.parametrize("raw,code", [
    ("", "empty"),
    ("javascript:alert(1)", "unsupported_scheme"),
    ("data:text/html,hi", "unsupported_scheme"),
    ("ftp://files.example.com/a", "unsupported_scheme"),
    ("file:///etc/passwd", "unsupported_scheme"),
    ("http://exa mple.com", "invalid_url"),
    ("http://", "invalid_host"),
    ("http://localhost/", "invalid_host"),
    ("http://example.notatld/", "invalid_host"),
    ("http://example.com:99999/", "invalid_url"),
    ("http://-bad-.com/", "invalid_host"),
    ("http://a.com/" + "x" * 5000, "too_long"),
])
def test_invalid_urls(raw, code):
    with pytest.raises(UrlValidationError) as e:
        parse_url(raw)
    assert e.value.code == code


def test_canonical_strips_scheme_www_and_root_slash():
    assert parse_url("https://www.example.com/").canonical == parse_url("http://example.com").canonical


@pytest.mark.parametrize("raw", ["http://2130706433/", "http://0x7f.1/", "http://0177.0.0.1/"])
def test_obfuscated_ipv4_is_decoded(raw):
    p = parse_url(raw)
    assert p.is_ip and p.ip_obfuscated and p.host == "127.0.0.1"


# ---------- look-alike domains & Unicode spoofing ----------
def test_cyrillic_homoglyph_of_apple():
    p = parse_url("https://xn--80ak6aa92e.com")  # "аррӏе.com" in Cyrillic letters
    assert p.host_unicode == "аррӏе.com"
    assert "homoglyph_brand" in ids("https://xn--80ak6aa92e.com")


def test_mixed_script_label_detected():
    # Latin "l" + Cyrillic "раура" -> mixed scripts in one label
    s = ids("https://раураl.com/login")
    assert {"mixed_script", "homoglyph_brand"} <= s


@pytest.mark.parametrize("url,brand", [
    ("http://paypa1.com", "paypal"),
    ("https://steamcommunlty.com/login", "steamcommunity"),
    ("https://kaspl.kz", "kaspi"),
    ("https://rnicrosoft.com", "microsoft"),
])
def test_typosquatting(url, brand):
    b = analyse_brand(parse_url(url))
    assert b.lookalike_target == brand


def test_brand_in_subdomain_and_combo():
    assert "brand_in_subdomain" in ids("http://kaspi.kz.secure-login.xyz/verify")
    assert "brand_in_domain" in ids("https://halyk-bonus.top/")


def test_official_domains_not_flagged_as_lookalike():
    for url in ("https://kaspi.kz/shop", "https://www.paypal.com/signin", "https://egov.kz"):
        s = ids(url)
        assert "official_domain" in s
        assert not s & {"typosquat_brand", "homoglyph_brand", "brand_in_domain"}


def test_user_content_host_is_not_official():
    s = ids("https://sites.google.com/view/kaspi-bonus")
    assert "user_content_hosting" in s and "official_domain" not in s


# ---------- suspicious parts ----------
def test_ip_host_and_userinfo_and_params():
    assert "ip_host" in ids("http://45.12.3.4/login")
    assert "userinfo_in_url" in ids("https://paypal.com@evil-site.com/")
    s = ids("https://example.org/a?email=user@mail.kz&next=https://evil-site.com")
    assert {"email_in_query", "open_redirect_param"} <= s
    assert "risky_download" in ids("https://example.org/update.apk")


def test_https_alone_is_not_evidence_of_safety():
    """Swapping http->https must not move a phishing-looking URL to a lower risk bucket."""
    http = rule_score(lexical_signals(parse_url("http://kaspi.kz.secure-login.xyz/verify")))
    https = rule_score(lexical_signals(parse_url("https://kaspi.kz.secure-login.xyz/verify")))
    assert https > 0.6 and http - https < 0.06


def test_feature_vector_is_complete_and_numeric():
    f = extract_features(parse_url("https://a.b.example.com/x/y.php?q=1"))
    assert list(f) == FEATURE_NAMES
    assert all(isinstance(v, float) for v in f.values())
