#!/usr/bin/env python3
"""R23: check the ORIGINAL creator's public Eula Shimeji attachment, not a mirror.

Eula is currently a missing source in the 123-person Genshin roster. Artist
SaylaMars directly posted the free desktop pet on FANBOX post 8264436:
https://www.reddit.com/r/EulaMains/comments/1e808mg/desktop_eula_pet/
No creator ZIP is assumed available: a page/link is NOT enough to promote a
source. Do not authenticate, evade access controls, execute JAR/EXE, redistribute
PNG, or print time-limited signed URLs, cookies or session credentials.
"""
from __future__ import annotations

import hashlib
import json
import re
import struct
from pathlib import Path, PurePosixPath
from io import BytesIO
import tempfile
import zipfile
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from zipfile import BadZipFile

from tools.install_personal_shimeji_zip import (
    inspect_shimeji_zip, install_personal_shimeji_zip)
from tools.creator_motion_quality import analyze_creator_actions
from tools.install_native_role import validate_native_role

PROFILE = "genshin_eula"
AUTHOR_ID = "saylamars"
POST_ID = "8264436"
AUTHOR_POST = "https://saylamars.fanbox.cc/posts/" + POST_ID
API_URL = "https://api.fanbox.cc/post.info?postId=" + POST_ID
MAX_METADATA = 512 * 1024
MAX_DOWNLOAD = 32 * 1024 * 1024
PUBLISHER_DOMAINS = frozenset((
    "downloads.fanbox.cc", "api.fanbox.cc", "fanbox.pixiv.net",
))
EXTENSIONS = frozenset((".zip",))


def _publisher_download_url(url):
    """Reject off-site, unsafe, insecure and injected original file URLs."""
    if not isinstance(url, str) or len(url) > 4096:
        return False
    try:
        parsed = urlsplit(url)
        return (parsed.scheme == "https" and
                parsed.hostname in PUBLISHER_DOMAINS and
                parsed.username is None and parsed.password is None and
                parsed.port in (None, 443) and not parsed.fragment)
    except ValueError:
        return False


def fetch_public_post(*, opener=urlopen):
    req = Request(API_URL, headers={
        "Origin": "https://www.fanbox.cc",
        "Referer": AUTHOR_POST,
        "User-Agent": "DyberPet-original-creator-public-asset-research/1",
        "Accept": "application/json",
    })
    with opener(req, timeout=20) as stream:
        final = urlsplit(stream.geturl())
        if final.scheme != "https" or final.hostname != "api.fanbox.cc":
            raise ValueError("Unexpected creator post metadata redirect")
        raw = stream.read(MAX_METADATA + 1)
    if not 0 < len(raw) <= MAX_METADATA:
        raise ValueError("Missing or excessive public creator metadata")
    obj = json.loads(raw.decode("utf-8"))
    if not isinstance(obj, dict):
        raise ValueError("Invalid creator metadata object")
    return obj


def extract_public_eula_post(reply):
    """Strict public artist/identity match. No public file => no source claim."""
    if not isinstance(reply, dict):
        raise ValueError("Invalid source response")
    wrapper = reply.get("body")
    if not isinstance(wrapper, dict):
        raise ValueError("Public Eula post unavailable without sign-in")
    # Current FANBOX public API uses {"body": {"post": {...}}}, while
    # older public clients expose the post directly under "body".
    post = wrapper.get("post", wrapper)
    if not isinstance(post, dict):
        raise ValueError("Public Eula post unavailable without sign-in")
    if str(post.get("id")) != POST_ID or post.get("creatorId") != AUTHOR_ID:
        raise ValueError("Wrong creator or post identity")
    if "eula" not in str(post.get("title", "")).lower():
        raise ValueError("Creator post is not explicitly about Eula")
    if post.get("isRestricted") is True:
        raise ValueError("Creator post is restricted: no authentication bypass")
    content = post.get("body")
    if not isinstance(content, dict):
        raise ValueError("No publicly accessible original attachment listing")
    candidates = []
    # FANBOX article uploads live under fileMap, not files. In this public
    # format the keys are article-specific IDs; only values are creator files.
    entries = content.get("files", [])
    file_map = content.get("fileMap", {})
    if not isinstance(entries, list) or not isinstance(file_map, dict):
        raise ValueError("Invalid public file listing")
    entries = entries[:25] + list(file_map.values())[:25]
    for f in entries:
        if not isinstance(f, dict):
            continue
        name = str(f.get("name", ""))[:180]
        ext = str(f.get("extension", "")).lower().lstrip(".")
        url = f.get("url")
        if (name.lower().endswith(".zip") or ext == "zip") and _publisher_download_url(url):
            candidates.append({"name": name, "url": url})
    # Keep post metadata and signed URLs private. Never print raw reply.
    return candidates


def download_creator_zip(url, *, opener=urlopen):
    if not _publisher_download_url(url):
        raise ValueError("Eula ZIP must be an original publisher HTTPS attachment")
    req = Request(url, headers={
        "Referer": AUTHOR_POST,
        "User-Agent": "DyberPet-original-creator-public-asset-research/1",
    })
    with opener(req, timeout=35) as result:
        final = result.geturl()
        if not _publisher_download_url(final):
            raise ValueError("Off-publisher original ZIP download redirect")
        data = result.read(MAX_DOWNLOAD + 1)
    if not isinstance(data, bytes) or not 0 < len(data) <= MAX_DOWNLOAD:
        raise ValueError("Creator ZIP missing or oversized")
    return data


def summarize_public_zip_layout(raw):
    """Unpack NOTHING: list bounded public filename evidence for format fixes."""
    with zipfile.ZipFile(BytesIO(raw)) as z:
        members = z.infolist()
        if len(members) > 1600 or sum(m.file_size for m in members) > 96 * 1024 * 1024:
            raise ValueError("Original Eula public archive exceeds safe inventory bounds")
        pngs = []
        configs = []
        numbered = {}
        dimensions = {}
        for item in members:
            name = item.filename.replace("\\\\", "/")
            parts = PurePosixPath(name).parts
            if (".." in parts or len(name) > 240 or name.startswith("/") or
                    item.file_size > 16 * 1024 * 1024):
                raise ValueError("Unsafe original creator archive path or member size")
            low = name.lower()
            if low.endswith(".png"):
                pngs.append(name)
                match = re.fullmatch(r"shime([1-9][0-9]*)\\.png",
                                     PurePosixPath(low).name)
                if match:
                    idx = int(match.group(1))
                    if idx in numbered:
                        raise ValueError("Duplicate original Eula sprite index")
                    numbered[idx] = name
                    with z.open(item) as stream:
                        head = stream.read(24)
                    if (len(head) == 24 and
                            head[:8] == b"\\x89PNG\\r\\n\\x1a\\n" and
                            head[12:16] == b"IHDR"):
                        dimensions[idx] = list(struct.unpack(">II", head[16:24]))
            elif low.endswith((".xml", ".json", ".properties", ".txt")):
                configs.append(name)
        return {
            "original_zip_entry_count": len(members),
            "original_png_count": len(pngs),
            "original_numbered_sprite_count": len(numbered),
            "original_numbered_sprite_min_max": (
                [min(numbered), max(numbered)] if numbered else []),
            "standard_first_46_missing": [
                i for i in range(1, 47) if i not in numbered
            ],
            "first_46_unique_dimensions": sorted(set(
                tuple(v) for i, v in dimensions.items() if i <= 46))[:20],
            "largest_original_sprite_dimensions": sorted(
                dimensions.values(), key=lambda x: x[0] * x[1],
                reverse=True)[:5],
            "original_png_name_examples": sorted(pngs)[:20],
            "original_config_name_examples": sorted(configs)[:15],
            "png_images_without_executing_code": True,
        }


def probe_eula(*, post_loader=None, downloader=None):
    obtain = post_loader if post_loader is not None else fetch_public_post
    post = obtain()
    links = extract_public_eula_post(post)
    state = {
        "scope": "original_Eula_creator_FANBOX_public_file_probe",
        "profile": PROFILE, "artist_author": AUTHOR_ID,
        "original_artist_post": AUTHOR_POST,
        "user_missing_roster_character": True,
        "public_publisher_zip_links": len(links),
        "identity_documentation_found": True,
        "source_registry_promoted": False,
        "official_character_likeness_verified": False,
        "rights_verified": False,
        "physical_desktop_playback_verified": False,
        "raw_url_or_artifact_uploaded": False,
    }
    if not links:
        wrapper = post.get("body") if isinstance(post, dict) else None
        page = wrapper.get("post", wrapper) if isinstance(wrapper, dict) else None
        content = page.get("body") if isinstance(page, dict) else None
        if isinstance(content, dict):
            field_map = content.get("fileMap", {})
            if isinstance(field_map, dict):
                state["public_filemap_entries"] = len(field_map)
            blocks = content.get("blocks", [])
            if isinstance(blocks, list):
                state["public_block_types"] = sorted(set(
                    str(row.get("type", ""))[:30] for row in blocks[:80]
                    if isinstance(row, dict)
                ))
            # Diagnostic ONLY: output field names of the public article, not
            # external URLs, download tokens, signed asset IDs or credentials.
            allowed = {"text", "blocks", "files", "fileMap", "imageMap",
                       "urlEmbedMap", "links", "type"}
            state["public_article_format"] = str(page.get("type", ""))[:30]
            state["public_article_field_names"] = sorted(
                str(k) for k in content if str(k) in allowed)
        state.update({"status": "public_creator_page_only_no_verified_original_ZIP",
                      "source_integrity_verified": False})
        return state
    if len(links) > 1:
        state.update({"status": "multiple_original_ZIPs_require_manual_choice",
                      "source_integrity_verified": False})
        return state
    loader = downloader if downloader is not None else download_creator_zip
    try:
        raw = loader(links[0]["url"])
    except (OSError, ValueError, TimeoutError) as exc:
        state.update({
            "status": "public_attachment_exists_but_cannot_download_without_credentials",
            "download_exception_class": type(exc).__name__,
            "source_integrity_verified": False})
        return state
    if not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_DOWNLOAD:
        raise ValueError("Invalid Eula source bytes")
    state["original_publisher_file_sha256"] = hashlib.sha256(raw).hexdigest()
    state["original_publisher_file_bytes"] = len(raw)
    with tempfile.TemporaryDirectory(prefix="dyberpet-original-eula-") as td:
        td = Path(td)
        archive = td / "artist.zip"
        archive.write_bytes(raw)
        try:
            frames = inspect_shimeji_zip(archive)
        except (BadZipFile, ValueError, OSError) as exc:
            state.update({
                "status": "public_creator_attachment_not_standard_shimeji_archive",
                "original_attachment_exception_class": type(exc).__name__,
                "source_integrity_verified": False})
            try:
                state["original_archive_layout"] = summarize_public_zip_layout(raw)
            except (BadZipFile, ValueError, OSError):
                state["original_archive_layout"] = {"safe_zip_layout_readable": False}
            return state
        try:
            role = install_personal_shimeji_zip(
                archive, td / "native", profile=PROFILE, confirmed=True)
        except (ValueError, OSError) as exc:
            state.update({
                "status": "original_creator_png_import_not_yet_accepted",
                "original_attachment_exception_class": type(exc).__name__,
                "original_png_frames": len(frames),
                "source_integrity_verified": False})
            return state
        validated = validate_native_role(role)
        motion = analyze_creator_actions(role.parent, role.name)
        receipt = json.loads(
            (role / "PERSONAL_IMPORT.json").read_text(encoding="utf-8"))
        if (receipt["selected_profile"] != PROFILE or
                receipt["source_archive_sha256"] != hashlib.sha256(raw).hexdigest() or
                receipt["all_original_frames_preserved"] != len(frames)):
            raise ValueError("Original Eula ZIP/native frame integrity mismatch")
        state.update({
            "status": "original_creator_public_ZIP_structurally_verified",
            "source_integrity_verified": True,
            "source_zip_sha256": hashlib.sha256(raw).hexdigest(),
            "source_zip_size": len(raw),
            "original_png_frames": len(frames),
            "native_actions": validated["actions"],
            "movement_poses": [
                {"action": a["action"], "frames": a["frame_count"],
                 "unique_visible_poses": a["unique_visible_poses"],
                 "risks": a["risk_indicators"]}
                for a in motion["actions"] if a["movement_expected"]
            ],
            "artist_filename_alone_proves_identity": False,
        })
        return state


def main():
    public_reply = None
    try:
        public_reply = fetch_public_post()
        report = probe_eula(post_loader=lambda: public_reply)
        print("ORIGINAL_EULA_CREATOR_SOURCE_PROBE " +
              json.dumps(report, ensure_ascii=False, sort_keys=True), flush=True)
        return 0 if report.get("source_integrity_verified") is True else 1
    except (HTTPError, URLError, OSError, ValueError, TypeError, KeyError,
            UnicodeError, TimeoutError) as exc:
        # Public response can be a login stub or a reduced metadata schema.
        # A PRIVATE token, URL or raw response body must never enter CI logs.
        reason = "public_artist_source_or_network_unavailable"
        if isinstance(exc, ValueError):
            for signal, code in (
                ("Public Eula post unavailable without sign-in",
                 "no_anonymous_public_post_metadata"),
                ("Wrong creator or post identity", "publisher_identity_not_matching"),
                ("not explicitly about Eula", "public_post_title_not_identified"),
                ("No publicly accessible original attachment listing",
                 "no_public_attachment_listing"),
                ("restricted: no authentication bypass",
                 "publisher_restricted_access"),
                ("Missing or excessive public creator metadata",
                 "publisher_metadata_empty_or_oversized"),
                ("Unexpected creator post metadata redirect",
                 "publisher_metadata_cross_site_redirect"),
                ("Invalid creator metadata object", "unexpected_public_metadata_shape"),
                ("Invalid public file listing", "publisher_attachment_schema_mismatch"),
                ("Off-publisher original ZIP download redirect",
                 "publisher_download_cross_site_redirect"),
                ("Eula ZIP must be an original publisher HTTPS attachment",
                 "original_attachment_host_not_allowlisted"),
                ("Creator ZIP missing or oversized", "original_attachment_oversized_or_missing"),
                ("Invalid Eula source bytes", "creator_asset_bytes_invalid"),
                ("Original artist attachment is not valid ZIP", "publisher_attachment_non_zip"),
                ("Not a compatible standard Shimeji archive",
                 "publisher_attachment_not_standard_shimeji"),
                ("walk frames are identical", "publisher_animation_pose_missing"),
                ("Original Eula ZIP/native frame integrity mismatch",
                 "native_import_source_frame_mismatch"),
            ):
                if signal in str(exc):
                    reason = code
                    break
        details = {}
        if reason == "publisher_identity_not_matching" and isinstance(public_reply, dict):
            wrapper = public_reply.get("body")
            post = wrapper.get("post", wrapper) if isinstance(wrapper, dict) else None
            if isinstance(post, dict):
                creator = post.get("creatorId")
                # The creator ID is publicly displayed post metadata, not a
                # time-limited file URL or an authentication token.
                if (isinstance(creator, str) and 0 < len(creator) <= 64 and
                        all(c.isascii() and (c.isalnum() or c in "-_")
                            for c in creator)):
                    details["public_post_creator_slug"] = creator
                details["post_id_matched"] = str(post.get("id")) == POST_ID
                details["title_mentions_eula"] = (
                    "eula" in str(post.get("title", "")).lower())
                # Field names only, never values from a publisher response
                # containing signed file URLs or private attachment tokens.
                details["public_body_field_names"] = sorted(
                    str(k) for k in post
                    if str(k) in ("id", "title", "creatorId", "post", "data",
                                   "error", "body", "status", "user", "creator",
                                   "isRestricted", "type", "message"))
        print("ORIGINAL_EULA_SOURCE_NOT_YET_VERIFIED " + json.dumps({
            "error_type": type(exc).__name__,
            "reason": reason,
            "http_status": getattr(exc, "code", None),
            "creator_page": AUTHOR_POST,
            "identity_diagnostic": details,
            "source_registry_promoted": False}, sort_keys=True), flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
