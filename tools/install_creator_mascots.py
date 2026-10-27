#!/usr/bin/env python3
"""Explicit one-click *personal* installation from pinned creator Codex sources.

Never called at startup or during packaged builds. The upstream source asset
is downloaded into a disposable directory with strict byte limits and pinned
checksums; it is NOT redistributed with the application. Individual creator
and underlying franchise rights remain separate from a download permission.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from pathlib import Path
from urllib.request import urlopen

try:
    from .chibi_profiles import available_role_folder
    from .import_codex_pet import convert
    from .install_native_role import validate_native_role
except ImportError:
    from chibi_profiles import available_role_folder
    from import_codex_pet import convert
    from install_native_role import validate_native_role

REPO="legeling/awesome-codex-pet"
PINNED_REVISION="db2f6306ce78f6559ab27155d7bfaf00bf43809d"
ROOT=f"https://raw.githubusercontent.com/{REPO}/{PINNED_REVISION}/pets"
UPSTREAM={
    "guga":{
        "id":"guga--circus","name":"咕嘎",
        "manifest_sha256":"3fbd12701d4d87f2c2bbed8f9ca79ecbf6924cbe071ed99f7af131f5e167483c",
        "atlas_sha256":"1b61ea2af98717b9ebe55beb4c6b820b89e9c42d4fdfeca21cf63ed3ad4e38da",
        "manifest_bytes":260,"atlas_bytes":1945586,
        "license":"Unknown; creator did not provide an explicit republication license",
    },
    "doro":{
        "id":"doro--lingxiaotian","name":"Doro",
        "manifest_sha256":"ea7e83e420d0a3c511531652bebdec748a47d38e59bbeaede11dd8f04fe08202",
        "atlas_sha256":"f0661f6f0b1297e54d40a33f0ecfa5c8ef76c88d5b92c4edd7dd76e9ca99872c",
        "manifest_bytes":242,"atlas_bytes":2382142,
        "license":"CC BY-NC 4.0 fan-art; underlying NIKKE/Dororong IP rights are separate",
    },
}
# An additional real author-drawn Doro V2 source. All exact bytes were
# retrieved from the immutable upstream revision and SHA-256 checked before
# allowing opt-in. Its source spritesheet (702066 B) was opened and inspected:
# pink hair, purple eyes, white quadruped and visible expression/pose changes.
# This is NOT a complete per-frame identity, motion or voice QA approval.
DORO_HANDDRAWN_V2 = {
    "id": "doro--godxxy1229", "name": "Doro",
    "manifest_sha256": "be11aebd66fd08974b13d2b2509ed16631aa30407078da3560b99504aa804fb1",
    "atlas_sha256": "a22d84a8836f60c535b7bf418eda5d68ba99ca36338f3816fc8a043b77bf3228",
    "manifest_bytes": 252, "atlas_bytes": 702066,
    "sprite_version": 2,
    "license": "Author permits non-commercial use only; underlying NIKKE rights remain separate",
}
DORO_VARIANTS = {
    "classic": UPSTREAM["doro"],
    "handdrawn_v2": DORO_HANDDRAWN_V2,
}
MAX_BYTES=6*1024*1024


def _download_pinned(url, sha256, expected_bytes, *, opener=urlopen):
    if expected_bytes > MAX_BYTES:
        raise ValueError("Pinned source exceeds size limit")
    with opener(url, timeout=15) as response:
        data=response.read(MAX_BYTES+1)
    if len(data)!=expected_bytes or len(data)>MAX_BYTES:
        raise ValueError("Unexpected source size; upstream may have changed")
    if hashlib.sha256(data).hexdigest()!=sha256:
        raise ValueError("Pinned source SHA-256 mismatch; refused changed artwork")
    return data


def install_creator_mascot(kind, output_root, *, confirmed=False,
                           folder=None, downloader=None, variant="classic"):
    """User-authorized local conversion. Do not call without a click/flag."""
    if not confirmed:
        raise ValueError("Personal-use source confirmation is required")
    if kind not in UPSTREAM:
        raise ValueError("Only reviewed Guga/Doro source IDs supported")
    if kind != "doro" and variant != "classic":
        raise ValueError("Doro V2 variant is only available for Doro")
    if variant not in DORO_VARIANTS:
        raise ValueError("Unknown pinned mascot variant")
    selected = DORO_VARIANTS[variant] if kind == "doro" else UPSTREAM[kind]
    root=Path(output_root).expanduser()
    if root.is_symlink():
        raise ValueError("Linked role roots are not supported")
    root=root.resolve()
    if folder is not None:
        import re
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,39}",folder):
            raise ValueError("Unsafe explicit output folder")
    suggested = ("SourceDoroHanddrawnV2" if kind == "doro" and
                 variant == "handdrawn_v2" else "Source" + kind.title())
    folder=folder or available_role_folder(root, suggested)
    target=root/folder
    if target.exists() or target.is_symlink():
        raise FileExistsError("Selected role already installed; refusing overwrite")
    get=downloader or _download_pinned
    roleid=selected["id"]
    url=f"{ROOT}/{roleid}"
    # The network and transformation occur in temporary storage. No public
    # upload, telemetry or generic URL/text injection is involved.
    root.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=root,prefix=".creator-source-") as staging:
        source=Path(staging)/roleid
        source.mkdir()
        for item,key in (("pet.json","manifest"),("spritesheet.webp","atlas")):
            blob=get(f"{url}/{item}",selected[key+"_sha256"],selected[key+"_bytes"])
            (source/item).write_bytes(blob)
        manifest=json.loads((source/"pet.json").read_text("utf-8"))
        if (manifest.get("id")!=roleid or
                manifest.get("spritesheetPath")!="spritesheet.webp" or
                manifest.get("spriteVersionNumber",1)!=selected.get("sprite_version",1)):
            raise ValueError("Remote Codex character ID/layout does not match pinned record")
        made=convert(source,root,preset=kind,folder=folder,style="classic",
                     preserve_source_frames=True,
                     source_url=f"https://github.com/{REPO}/tree/{PINNED_REVISION}/pets/{roleid}",
                     license_name=selected["license"])
    info=validate_native_role(made)
    # Match the other artist installers: keep a bounded, explicit local
    # identity receipt. This is provenance, not manual likeness approval.
    (made / "PERSONAL_IMPORT.json").write_text(
        json.dumps({"display_name": selected["name"],
                    "selected_profile": kind,
                    "source_id": roleid,
                    "source_repository": REPO,
                    "source_commit": PINNED_REVISION,
                    "source_kind": "curated_creator_spritesheet",
                    "source_variant": variant,
                    "preserve_source_frames": True,
                    "likeness_manually_reviewed": False,
                    "source_rights_verified": False},
                   ensure_ascii=False, indent=2), encoding="utf-8")
    return {"kind":kind,"folder":made.name,"source_id":roleid,
            "source_variant": variant,
            "actions":info["actions"],"frames":info["images"],
            "downloaded_for_user_only":True,"built_into_app":False,
            "faithful_art_manual_qa_required":True,
            "permission_to_redistribute_not_granted":True,
            "voice_included":False}


def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--mascot",choices=sorted(UPSTREAM),required=True)
    ap.add_argument("--output-root",type=Path,default=Path("res/role"))
    ap.add_argument("--variant", choices=tuple(DORO_VARIANTS), default="classic",
                    help="For Doro: optional exact-pinned handdrawn_v2 sprites (no voice)")
    ap.add_argument("--personal-use",action="store_true",
                    help="Consent to fetching this one public creator pet for local use")
    args=ap.parse_args(argv)
    try:
        print(json.dumps(install_creator_mascot(
            args.mascot,args.output_root,confirmed=args.personal_use,
            variant=args.variant),
            ensure_ascii=False))
    except (OSError,ValueError,FileNotFoundError) as exc:
        ap.exit(1,"Personal creator download blocked: "+str(exc)+"\n")


if __name__=="__main__":
    raise SystemExit(main())
