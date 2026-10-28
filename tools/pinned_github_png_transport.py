"""Fallback transport for exact-hash-pinned public GitHub original PNG frames.

This ONLY improves HTTPS reachability for already recorded original PNG bytes.
It never permits a new character/persona, unverified original URL, synthetic
picture, script execution or any mismatch with the pinned Git blob hash.

A failed raw.githubusercontent.com request may be retried via a *fixed*
GitHub media endpoint and then jsDelivr for the SAME immutable commit/path.
Every returned source still passes the caller's byte-size/Git blob verifier.
"""
from __future__ import annotations

import re
import threading
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

MAX_PATH = 900
TRUSTED_RESPONSE_HOSTS = frozenset((
    "raw.githubusercontent.com",
    "media.githubusercontent.com",
    "cdn.jsdelivr.net",
    "fastly.jsdelivr.net",
))
_HOST_CHOICES = ("raw", "media", "jsdelivr")
_PREFERRED = {}
_LOCK = threading.Lock()


def _source_paths(original):
    if not isinstance(original, str) or len(original) > 1600:
        return None
    parsed = urlsplit(original)
    if (parsed.scheme != "https" or parsed.hostname != "raw.githubusercontent.com"
            or parsed.username or parsed.password or parsed.port
            or parsed.query or parsed.fragment or not parsed.path.startswith("/")):
        return None
    parts = parsed.path.strip("/").split("/", 3)
    if len(parts) != 4 or len(parts[3]) > MAX_PATH:
        return None
    owner, repo, commit, relative = parts
    if (not re.fullmatch(r"[A-Za-z0-9_.-]{1,100}", owner)
            or not re.fullmatch(r"[A-Za-z0-9_.-]{1,100}", repo)
            or not re.fullmatch(r"[0-9a-f]{40}", commit)
            or "%" in relative or "\\" in relative
            or any(p in ("", ".", "..") for p in relative.split("/"))):
        return None
    return (owner, repo, commit, relative)


def pinned_github_png_urls(url):
    """Return only the original and two immutable-equivalent public URLs."""
    parsed = _source_paths(url)
    if parsed is None:
        return (url,)
    owner, repo, commit, relative = parsed
    return (
        url,
        f"https://media.githubusercontent.com/media/{owner}/{repo}/{commit}/{relative}",
        f"https://cdn.jsdelivr.net/gh/{owner}/{repo}@{commit}/{relative}",
    )


def _read_source(address, limit, opener):
    req = Request(address, headers={"User-Agent": "DyberPet-immutable-creator-png/1"})
    with opener(req, timeout=30) as stream:
        dest = stream.geturl() if hasattr(stream, "geturl") else address
        uri = urlsplit(dest)
        if (uri.scheme != "https" or uri.hostname not in TRUSTED_RESPONSE_HOSTS
                or uri.username or uri.password):
            raise ValueError("Untrusted artist PNG download redirect")
        data = stream.read(limit + 1)
    if not isinstance(data, bytes) or len(data) > limit:
        raise ValueError("Creator PNG exceeds bounded read")
    return data


def download_pinned_github_png(url, limit, *, opener=urlopen):
    """Fail closed on invalid content; only network errors trigger mirrors.

    Source integrity is NOT checked here: the caller must check Git-blob SHA1,
    expected bytes and PNG dimensions before installing or writing to disk.
    """
    if not isinstance(limit, int) or not 1 <= limit <= 8 * 1024 * 1024:
        raise ValueError("Unsafe PNG downloader size bound")
    addresses = pinned_github_png_urls(url)
    if len(addresses) == 1:
        # No alternate origin for arbitrary / non-immutable external URLs.
        return _read_source(addresses[0], limit, opener)
    parsed = _source_paths(url)
    key = parsed[:3]
    with _LOCK:
        preferred = _PREFERRED.get(key)
    order = list(range(len(addresses)))
    if preferred is not None and preferred in order:
        order.remove(preferred)
        order.insert(0, preferred)
    errors = []
    for index in order:
        try:
            data = _read_source(addresses[index], limit, opener)
        except (OSError, TimeoutError, URLError, ConnectionError) as exc:
            # Only reachability errors justify a network alternate. Never
            # suppress unsafe redirect, truncated/bad content or bad hashes.
            errors.append(f"{_HOST_CHOICES[index]}:{type(exc).__name__}")
            continue
        with _LOCK:
            _PREFERRED[key] = index
        return data
    raise OSError("Pinned creator GitHub source unavailable on raw/media/jsdelivr "
                  "(" + ", ".join(errors) + "); immutable original not installed")


def reset_transport_preference_for_tests():
    with _LOCK:
        _PREFERRED.clear()


def download_pinned_github_asset(url, limit, *, opener=urlopen):
    """Transport immutable GitHub JSON/WebP/PNG byte objects without re-encoding.

    The separate caller MUST check its known Git blob SHA-1 and byte length
    before consuming the result. Network fallback never relaxes identity.
    """
    return download_pinned_github_png(url, limit, opener=opener)
