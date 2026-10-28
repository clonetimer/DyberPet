"""Manual Q-chibi three-view intake and immutable pre-build guard.

Only paths, hashes and review attestations are stored in a git-ignored case file.
This cannot establish character likeness or art rights automatically.
"""
import hashlib
import json
from pathlib import Path
from PIL import Image, UnidentifiedImageError

VIEWS = ("front", "side", "back")
CHECKS = ("silhouette", "outfit", "identity", "cross_view")


class TurnaroundError(ValueError):
    pass


def _view(path):
    supplied = Path(path).expanduser()
    if supplied.is_symlink() or not supplied.is_file():
        raise TurnaroundError("Turnaround must be three regular local image files, not links")
    file = supplied.resolve()
    if not 0 < file.stat().st_size <= 20 * 1024 * 1024:
        raise TurnaroundError("Turnaround image must be at most 20 MiB")
    try:
        with Image.open(file) as im:
            im.verify()
        with Image.open(file) as im:
            w, h, fmt = im.width, im.height, im.format
    except (OSError, ValueError, UnidentifiedImageError) as exc:
        raise TurnaroundError("Invalid turnaround image: " + file.name) from exc
    if fmt not in ("PNG", "JPEG", "WEBP") or not (64 <= w <= 4096 and 64 <= h <= 4096):
        raise TurnaroundError("Turnaround requires PNG/JPEG/WebP 64–4096px per side")
    sha = hashlib.sha256(file.read_bytes()).hexdigest()
    return {"path": str(file), "sha256": sha, "size": [w, h]}


def _signature(sheet):
    immutable = {
        "reference_url": sheet["reference_url"],
        "artist": sheet["artist"],
        "variant": sheet["variant"],
        "views": {v: sheet["views"][v]["sha256"] for v in VIEWS},
    }
    return hashlib.sha256(json.dumps(
        immutable, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def capture(front, side, back, *, reference_url, artist, variant):
    if not reference_url.startswith("https://") or not reference_url[8:].strip():
        raise TurnaroundError("A specific HTTPS turnaround source URL is mandatory")
    if not artist.strip() or not variant.strip():
        raise TurnaroundError("Turnaround artist and costume/version are required")
    views = {v: _view(p) for v, p in zip(VIEWS, (front, side, back))}
    if len({views[v]["sha256"] for v in VIEWS}) != 3:
        raise TurnaroundError("Front, side and back must be three distinct crops/images")
    return {"reference_url": reference_url, "artist": artist.strip(),
            "variant": variant.strip(), "views": views, "review": {}}


def verify(sheet):
    if not isinstance(sheet, dict) or not all(sheet.get(k) for k in (
            "reference_url", "artist", "variant", "views")):
        raise TurnaroundError("Q-chibi turnaround missing: attach front/side/back")
    try:
        for v in VIEWS:
            if _view(sheet["views"][v]["path"]) != sheet["views"][v]:
                raise TurnaroundError("Turnaround image changed: " + v)
        if len({sheet["views"][v]["sha256"] for v in VIEWS}) != 3:
            raise TurnaroundError("Duplicate turnaround reference views")
        review = sheet.get("review") or {}
        if not review.get("reviewer") or not all(
                review.get("checks", {}).get(k) is True for k in CHECKS):
            raise TurnaroundError("Human Q-chibi front/side/back approval required")
        if review.get("signature") != _signature(sheet):
            raise TurnaroundError("Turnaround approval is stale; re-review")
    except (KeyError, TypeError, OSError) as exc:
        raise TurnaroundError("Turnaround source views missing or invalid") from exc
    return sheet


def approve(sheet, reviewer, checks, date):
    if not reviewer.strip() or not all(checks.get(k) is True for k in CHECKS):
        raise TurnaroundError("Reviewer and all four visual checks are required")
    # Validate the current source before writing an approval.
    if not sheet.get("views"):
        raise TurnaroundError("Attach all three views before review")
    for v in VIEWS:
        if _view(sheet["views"][v]["path"]) != sheet["views"][v]:
            raise TurnaroundError("Changed view; attach a fresh turnaround")
    sheet["review"] = {"reviewer": reviewer.strip(), "reviewed_on": date,
                       "checks": {k: True for k in CHECKS},
                       "signature": _signature(sheet)}
    return sheet


def release_metadata(sheet):
    verify(sheet)
    return {"reference_url": sheet["reference_url"], "artist": sheet["artist"],
            "variant": sheet["variant"], "view_sha256": {
                k: sheet["views"][k]["sha256"] for k in VIEWS},
            "reviewer": sheet["review"]["reviewer"]}
