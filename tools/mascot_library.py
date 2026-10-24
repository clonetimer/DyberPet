"""Read-only original-demo vs creator-supplied Codex art inventory for Guga/Doro."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

try:
    from .generate_mascot_demos import MASCOTS
    from .install_native_role import inspect_native_folder
    from .role_family import known_mascot_family
except ImportError:
    from generate_mascot_demos import MASCOTS
    from install_native_role import inspect_native_folder
    from role_family import known_mascot_family

SOURCE_IDS={"guga":"guga--circus","doro":"doro--lingxiaotian"}
MAX_JSON=128*1024


def _load_report(path):
    if path.is_symlink() or not path.is_file():
        return None
    if path.stat().st_size>MAX_JSON:
        raise ValueError("Mascot receipt too large")
    record=json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(record,dict):
        raise ValueError("Mascot receipt must be JSON object")
    return record


def scan_mascot_library(role_root):
    root=Path(role_root).expanduser()
    if root.is_symlink():
        raise ValueError("Linked role root not allowed")
    if root.exists() and not root.is_dir():
        raise ValueError("Local role root is not a directory")
    items={key:{"key":key,"display_name":meta["name"],
                "original_demos":[],"imported_creator_art":[],
                "official_identity_verified":False,"voice_verified":False,
                "rights_verified":False}
           for key,meta in MASCOTS.items()}
    issues=[]
    if root.exists():
        for folder in sorted(root.iterdir(),key=lambda x:x.name.casefold()):
            if folder.is_symlink():
                issues.append({"folder":folder.name,"reason":"linked_role"})
                continue
            if not folder.is_dir() or folder.name.startswith("."):
                continue
            try:
                known_identity=known_mascot_family(folder)
                if known_identity is None:
                    continue
                demo=_load_report(folder/"BUILTIN_MASCOT_DEMO.json")
                original=_load_report(folder/"IMPORT_REPORT.json")
                identified=None
                category=None
                if demo is not None:
                    identified=demo.get("mascot")
                    if (identified not in items or
                            demo.get("generator")!="DyberPet-first-party-mascot-chibi-v1" or
                            demo.get("original_geometry") is not True or
                            demo.get("external_artist_sprite_included") is not False):
                        raise ValueError("Invalid first-party mascot marker")
                    if folder.name!=MASCOTS[identified]["folder"]:
                        raise ValueError("Built-in demo marker has wrong role folder")
                    category="original_demos"
                elif original is not None and original.get("mascot_preset") in SOURCE_IDS:
                    identified=original["mascot_preset"]
                    if original.get("source_manifest_id")!=SOURCE_IDS[identified]:
                        raise ValueError("Codex mascot preset does not match source ID")
                    category="imported_creator_art"
                if category is None or identified != known_identity:
                    raise ValueError("Mascot receipt classification conflicts with origin")
                valid=inspect_native_folder(folder)["validation"]
                items[identified][category].append({
                    "folder":folder.name,
                    "actions":valid["actions"],"frames":valid["images"],
                    "likeness_verified":False,"rights_verified":False,
                })
            except (ValueError,OSError,UnicodeError,TypeError,
                    json.JSONDecodeError) as exc:
                issues.append({"folder":folder.name,"reason":"invalid_role",
                               "detail":str(exc)[:160]})
    summary={
        "mascot_count":len(items),
        "original_demo_count":sum(bool(x["original_demos"]) for x in items.values()),
        "imported_creator_art_count":sum(bool(x["imported_creator_art"]) for x in items.values()),
        "missing_demo_count":sum(not x["original_demos"] for x in items.values()),
        "invalid_count":len(issues),
        "character_likeness_verified":False,
    }
    return {"scope":"read_only_local",
            "summary":summary,"mascots":list(items.values()),"invalid_local":issues,
            "note":"Original demos are playable layouts, not Guga/Doro source artwork or voice"}


def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--role-root",type=Path,default=Path("res/role"))
    args=ap.parse_args(argv)
    report=scan_mascot_library(args.role_root)
    print(json.dumps(report,ensure_ascii=False,indent=2))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
