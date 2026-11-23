"""Small string utilities: entropy, edit distance, confusable skeletons, scripts."""

from __future__ import annotations

import math
import unicodedata
from collections import Counter

from .data_lists import CONFUSABLES, MULTI_CONFUSABLES


def shannon_entropy(s: str) -> float:
    if not s:
        return 0.0
    counts = Counter(s)
    n = len(s)
    return -sum(c / n * math.log2(c / n) for c in counts.values())


def damerau_levenshtein(a: str, b: str, max_dist: int = 3) -> int:
    """Optimal string alignment distance with early exit above max_dist."""
    if a == b:
        return 0
    if abs(len(a) - len(b)) > max_dist:
        return max_dist + 1
    prev2: list[int] | None = None
    prev = list(range(len(b) + 1))
    for i in range(1, len(a) + 1):
        cur = [i] + [0] * len(b)
        row_min = cur[0]
        for j in range(1, len(b) + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost)
            if prev2 is not None and i > 1 and j > 1 and a[i - 1] == b[j - 2] and a[i - 2] == b[j - 1]:
                cur[j] = min(cur[j], prev2[j - 2] + 1)
            row_min = min(row_min, cur[j])
        if row_min > max_dist:
            return max_dist + 1
        prev2, prev = prev, cur
    return prev[-1]


def skeleton(s: str) -> str:
    """Map visually confusable characters to an ASCII skeleton (lowercase)."""
    s = unicodedata.normalize("NFKC", s.lower())
    out = "".join(CONFUSABLES.get(ch, ch) for ch in s)
    for src, dst in MULTI_CONFUSABLES:
        out = out.replace(src, dst)
    return out.replace("-", "")


def char_script(ch: str) -> str:
    if ch.isascii():
        return "LATIN" if ch.isalpha() else "COMMON"
    try:
        name = unicodedata.name(ch)
    except ValueError:
        return "UNKNOWN"
    for script in ("CYRILLIC", "GREEK", "LATIN", "ARMENIAN", "ARABIC", "HEBREW", "CJK", "HANGUL"):
        if script in name:
            return script
    return "OTHER"


def scripts_in(label: str) -> set[str]:
    return {sc for sc in (char_script(c) for c in label) if sc not in ("COMMON",)}


def longest_repeat_run(s: str) -> int:
    best = run = 0
    prev = ""
    for ch in s:
        run = run + 1 if ch == prev else 1
        prev = ch
        best = max(best, run)
    return best
