"""Brand impersonation analysis: homoglyphs, typosquatting, combo-squatting."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import idna

from .data_lists import BRAND_TOKENS, BRANDS, OFFICIAL_DOMAINS
from .normalize import ParsedUrl
from .text_utils import damerau_levenshtein, scripts_in, skeleton

_WORD_SPLIT = re.compile(r"[^a-z]+")

# label -> brand, built from official domains ("paypal" -> "paypal")
_OFFICIAL_LABELS: dict[str, str] = {}
for _brand, _domains in BRANDS.items():
    for _d in _domains:
        _lbl = _d.split(".")[0]
        if len(_lbl) >= 4:
            _OFFICIAL_LABELS.setdefault(_lbl, _brand)
_OFFICIAL_SKELETONS: dict[str, str] = {skeleton(lbl): lbl for lbl in _OFFICIAL_LABELS}

# Extra official infrastructure domains so that brand tokens inside them do not
# trigger combo-squatting alarms.
_EXTRA_OFFICIAL = {
    "googleapis.com", "googleusercontent.com", "gstatic.com", "googlevideo.com",
    "appleid.apple.com", "apple-cloudkit.com", "microsoftonline.com", "msftauth.net",
    "paypalobjects.com", "fbcdn.net", "cdninstagram.com", "steamstatic.com",
    "kaspi.kz", "steamcontent.com", "yandex.net", "kaspi-pay.kz",
}


@dataclass
class BrandFindings:
    official_domain: bool = False
    lookalike_brand: str | None = None  # brand whose domain is imitated
    lookalike_kind: str | None = None  # "homoglyph" | "typosquat"
    lookalike_target: str | None = None  # official label imitated, e.g. "paypal"
    combo_brand: str | None = None  # brand token embedded in unofficial domain label
    subdomain_brand: str | None = None  # brand token in subdomain of unofficial domain
    path_brand: str | None = None  # brand token as a path word on unofficial domain
    mixed_script: bool = False
    non_ascii: bool = False
    scripts: list[str] = field(default_factory=list)


def _unicode_label(label: str) -> str:
    if label.startswith("xn--"):
        try:
            return idna.decode(label)
        except idna.IDNAError:
            return label
    return label


def _words(s: str) -> list[str]:
    return [w for w in _WORD_SPLIT.split(s.lower()) if w]


def _token_in_words(words: list[str]) -> str | None:
    for w in words:
        for tok in BRAND_TOKENS:
            if w == tok or (len(tok) >= 5 and (w.startswith(tok) or w.endswith(tok))):
                return tok
    return None


def analyse_brand(p: ParsedUrl) -> BrandFindings:
    f = BrandFindings()
    if p.is_ip:
        f.path_brand = _token_in_words(_words(p.path))
        return f

    reg = p.registered_domain
    f.official_domain = reg in OFFICIAL_DOMAINS or reg in _EXTRA_OFFICIAL
    label_u = _unicode_label(p.domain_label)
    f.non_ascii = not p.host_unicode.isascii()
    for lbl in p.host_unicode.split("."):
        sc = scripts_in(lbl)
        if len(sc) > 1:
            f.mixed_script = True
        f.scripts = sorted(set(f.scripts) | sc)

    if not f.official_domain:
        # 1) Homoglyph / look-alike of an official label
        sk = skeleton(label_u)
        target = _OFFICIAL_SKELETONS.get(sk)
        if target and label_u != target:
            f.lookalike_brand = _OFFICIAL_LABELS[target]
            f.lookalike_target = target
            f.lookalike_kind = "homoglyph" if not label_u.isascii() else "typosquat"
        else:
            # 2) Typosquatting by edit distance
            for off_label, brand in _OFFICIAL_LABELS.items():
                if len(off_label) < 5 or label_u == off_label:
                    continue
                limit = 1 if len(off_label) < 9 else 2
                if damerau_levenshtein(label_u, off_label, limit) <= limit:
                    f.lookalike_brand, f.lookalike_target, f.lookalike_kind = brand, off_label, "typosquat"
                    break
        # 3) Combo-squatting: brand token inside the registered label
        if not f.lookalike_brand:
            f.combo_brand = _token_in_words(_words(skeleton(label_u)) if not label_u.isascii() else [label_u])
            if f.combo_brand is None:
                f.combo_brand = _token_in_words(_words(label_u.replace("-", " ")))
        # 4) Brand in subdomain (e.g. paypal.com.secure-login.xyz)
        if p.subdomain:
            f.subdomain_brand = _token_in_words(_words(p.subdomain))
        # 5) Brand in path
        f.path_brand = _token_in_words(_words(p.path))
    return f
