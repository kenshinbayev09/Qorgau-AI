"""Static reference lists used by URL heuristics and feature extraction.

These lists are hand-curated for an educational MVP. They are NOT a reputation
feed: a domain being absent from them says nothing about its safety.
"""

from __future__ import annotations

# Official registered domains of frequently impersonated brands.
# Key = brand token (used for "brand appears in host/path" checks),
# value = set of official registered domains for that brand.
BRANDS: dict[str, set[str]] = {
    # Global
    "google": {"google.com", "google.kz", "google.ru", "gmail.com", "youtube.com", "goo.gl"},
    "gmail": {"gmail.com", "google.com"},
    "youtube": {"youtube.com", "youtu.be", "google.com"},
    "facebook": {"facebook.com", "fb.com", "fb.me", "meta.com"},
    "instagram": {"instagram.com"},
    "whatsapp": {"whatsapp.com", "whatsapp.net", "wa.me"},
    "telegram": {"telegram.org", "t.me", "telegram.me"},
    "apple": {"apple.com", "icloud.com"},
    "icloud": {"icloud.com", "apple.com"},
    "microsoft": {"microsoft.com", "live.com", "outlook.com", "office.com", "microsoftonline.com", "windows.net"},
    "outlook": {"outlook.com", "live.com", "office.com", "microsoft.com"},
    "office365": {"office.com", "microsoft.com", "microsoftonline.com"},
    "amazon": {"amazon.com", "amazon.de", "amazon.co.uk", "amazonaws.com"},
    "paypal": {"paypal.com", "paypal.me"},
    "netflix": {"netflix.com"},
    "linkedin": {"linkedin.com", "lnkd.in"},
    "twitter": {"twitter.com", "x.com", "t.co"},
    "tiktok": {"tiktok.com"},
    "yandex": {"yandex.ru", "yandex.kz", "yandex.com", "ya.ru"},
    "mailru": {"mail.ru"},
    "vkontakte": {"vk.com"},
    "ebay": {"ebay.com"},
    "dropbox": {"dropbox.com"},
    "github": {"github.com", "github.io"},
    "binance": {"binance.com"},
    "coinbase": {"coinbase.com"},
    "metamask": {"metamask.io"},
    "steam": {"steampowered.com", "steamcommunity.com"},
    "steamcommunity": {"steamcommunity.com"},
    "booking": {"booking.com"},
    "aliexpress": {"aliexpress.com", "aliexpress.ru"},
    "wildberries": {"wildberries.ru", "wildberries.kz", "wb.ru"},
    "ozon": {"ozon.ru", "ozon.kz"},
    "sberbank": {"sberbank.ru", "sber.ru"},
    "tinkoff": {"tinkoff.ru", "tbank.ru"},
    "gosuslugi": {"gosuslugi.ru"},
    "docusign": {"docusign.com", "docusign.net"},
    "wetransfer": {"wetransfer.com"},
    "adobe": {"adobe.com"},
    "dhl": {"dhl.com", "dhl.de"},
    "fedex": {"fedex.com"},
    # Kazakhstan
    "kaspi": {"kaspi.kz"},
    "halyk": {"halykbank.kz", "homebank.kz"},
    "halykbank": {"halykbank.kz", "homebank.kz"},
    "homebank": {"homebank.kz", "halykbank.kz"},
    "egov": {"egov.kz", "gov.kz"},
    "jusan": {"jusan.kz", "jusanbank.kz"},
    "forte": {"forte.kz", "fortebank.com"},
    "fortebank": {"forte.kz", "fortebank.com"},
    "freedom": {"freedombank.kz", "ffin.kz", "freedom24.com"},
    "kazpost": {"post.kz", "kazpost.kz"},
    "kolesa": {"kolesa.kz"},
    "krisha": {"krisha.kz"},
    "olx": {"olx.kz", "olx.ua", "olx.pl"},
    "beeline": {"beeline.kz", "beeline.ru"},
    "kcell": {"kcell.kz", "activ.kz"},
    "chocotravel": {"chocotravel.com"},
    "bcc": {"bcc.kz"},
}

# Flattened set of official registered domains.
OFFICIAL_DOMAINS: set[str] = {d for domains in BRANDS.values() for d in domains}

# Brand tokens long enough for substring checks (short ones cause false hits).
BRAND_TOKENS: list[str] = sorted({b for b in BRANDS if len(b) >= 4}, key=len, reverse=True)

# Multi-tenant hosting where anyone can publish content. A URL on these hosts
# is NOT vouched for by the hosting company.
USER_CONTENT_HOSTS: set[str] = {
    "firebaseapp.com", "web.app", "github.io", "gitlab.io", "pages.dev", "workers.dev",
    "netlify.app", "vercel.app", "herokuapp.com", "glitch.me", "repl.co", "replit.dev",
    "replit.app", "000webhostapp.com", "weebly.com", "weeblysite.com", "wixsite.com",
    "blogspot.com", "ipfs.io", "infura-ipfs.io", "cloudflare-ipfs.com", "dweb.link",
    "azurewebsites.net", "web.core.windows.net", "appspot.com", "square.site",
    "webflow.io", "framer.app", "framer.website", "ngrok.io", "ngrok-free.app",
    "trycloudflare.com", "duckdns.org", "translate.goog", "r2.dev", "surge.sh",
    "godaddysites.com", "mybluehost.me", "wordpress.com", "tilda.ws", "notion.site",
    "carrd.co", "jimdosite.com", "s3.amazonaws.com", "storage.googleapis.com",
}
# Specific hosts on otherwise official domains that serve user content.
USER_CONTENT_EXACT_HOSTS: set[str] = {
    "sites.google.com", "docs.google.com", "drive.google.com", "forms.gle",
    "script.google.com", "firebasestorage.googleapis.com", "1drv.ms",
    "onedrive.live.com", "dropbox.com", "dl.dropboxusercontent.com",
}

URL_SHORTENERS: set[str] = {
    "bit.ly", "bitly.com", "tinyurl.com", "t.co", "goo.gl", "is.gd", "cutt.ly", "rb.gy",
    "ow.ly", "shorturl.at", "tiny.cc", "rebrand.ly", "clck.ru", "vk.cc", "u.to", "s.id",
    "buff.ly", "lnkd.in", "v.gd", "qr.net", "shorte.st", "adf.ly", "bl.ink", "t.ly",
    "app.link", "linktr.ee", "surl.li", "kutt.it",
}

# TLDs that appear disproportionately often in abuse reports. Membership is a
# weak signal only; many legitimate sites use these TLDs.
ABUSED_TLDS: set[str] = {
    "zip", "mov", "top", "xyz", "tk", "ml", "ga", "cf", "gq", "icu", "cyou", "buzz",
    "click", "link", "rest", "sbs", "cfd", "lol", "monster", "quest", "support",
    "online", "site", "website", "fun", "work", "country", "kim", "men", "loan",
    "gdn", "bid", "win", "review", "date", "racing", "download", "stream", "cam",
    "bond", "autos", "beauty", "hair", "skin", "boats", "mom", "yachts", "best",
}

SUSPICIOUS_KEYWORDS: tuple[str, ...] = (
    "login", "log-in", "signin", "sign-in", "logon", "verify", "verification",
    "secure", "security", "account", "update", "confirm", "password", "passwd",
    "banking", "wallet", "recover", "unlock", "suspend", "billing", "invoice",
    "payment", "authenticate", "webscr", "credential", "validate", "restore",
    "limited", "alert", "unusual", "bonus", "prize", "giveaway", "airdrop",
    "claim", "refund", "seed", "otp", "2fa", "kyc", "vhod", "oplata", "podtverd",
    "akkaunt", "parol", "vyigr", "kompens",
)

# Query parameter names that commonly carry secrets; their values are never
# logged and never echoed back in full.
SECRET_PARAM_NAMES: set[str] = {
    "token", "access_token", "id_token", "refresh_token", "auth", "authorization",
    "key", "api_key", "apikey", "secret", "password", "passwd", "pwd", "pass",
    "session", "sessionid", "sid", "code", "otp", "sig", "signature", "jwt",
    "email", "mail", "phone", "user", "username", "login",
}

REDIRECT_PARAM_NAMES: set[str] = {
    "url", "redirect", "redirect_uri", "redirect_url", "redir", "next", "return",
    "returnurl", "return_url", "goto", "target", "dest", "destination", "continue",
    "u", "out", "link", "to",
}

RISKY_FILE_EXTENSIONS: tuple[str, ...] = (
    ".exe", ".apk", ".scr", ".msi", ".bat", ".cmd", ".js", ".vbs", ".jar", ".ps1",
    ".dmg", ".pkg", ".iso", ".img", ".hta", ".lnk", ".xapk",
)

# Hosts of social networks / video platforms: a link to them is a *page*, not
# a direct media file, so deepfake analysis needs the user to upload the file.
SOCIAL_MEDIA_HOSTS: set[str] = {
    "instagram.com", "tiktok.com", "youtube.com", "youtu.be", "facebook.com", "fb.watch",
    "x.com", "twitter.com", "t.me", "vk.com", "ok.ru", "threads.net", "reddit.com",
    "snapchat.com", "pinterest.com", "linkedin.com", "twitch.tv", "rutube.ru",
}

# Visually confusable characters mapped to an ASCII "skeleton".
# Covers common Cyrillic/Greek/Latin-extended look-alikes and digit swaps.
CONFUSABLES: dict[str, str] = {
    # Cyrillic
    "а": "a", "в": "b", "е": "e", "ё": "e", "к": "k", "м": "m", "н": "h", "о": "o",
    "р": "p", "с": "c", "т": "t", "у": "y", "х": "x", "і": "i", "ї": "i", "ј": "j",
    "ѕ": "s", "ԁ": "d", "ԛ": "q", "ԝ": "w", "һ": "h", "ӏ": "l", "ɡ": "g", "ү": "y",
    "ң": "h", "қ": "k", "ө": "o", "ұ": "y", "ә": "a",
    # Greek
    "α": "a", "β": "b", "ε": "e", "ι": "i", "κ": "k", "ν": "v", "ο": "o", "ρ": "p",
    "τ": "t", "υ": "u", "χ": "x", "ω": "w",
    # Latin extended / accents
    "á": "a", "à": "a", "â": "a", "ä": "a", "ã": "a", "å": "a", "ą": "a",
    "é": "e", "è": "e", "ê": "e", "ë": "e", "ę": "e", "í": "i", "ì": "i", "î": "i",
    "ï": "i", "ı": "i", "ó": "o", "ò": "o", "ô": "o", "ö": "o", "õ": "o", "ø": "o",
    "ú": "u", "ù": "u", "û": "u", "ü": "u", "ç": "c", "ñ": "n", "ś": "s", "ș": "s",
    "ş": "s", "ž": "z", "ł": "l", "ğ": "g",
    # Digit/letter swaps
    "0": "o", "1": "l", "3": "e", "5": "s", "@": "a", "$": "s",
}
# Multi-character confusables applied after single-char mapping.
MULTI_CONFUSABLES: tuple[tuple[str, str], ...] = (("rn", "m"), ("vv", "w"), ("cl", "d"), ("ii", "u"))
