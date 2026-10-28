"""Install existing public Codex Pets sprites, keeping original pixel art.

Uses two exact Git-blob-pinned files per character from legeling's maintained
collection. Conversion crops the artist's spritesheet, not procedural drawings.
Downloaded files are installed locally on user request only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import tempfile
from urllib.request import Request, urlopen

try:
    from .import_codex_pet import convert
    from .install_native_role import validate_native_role
    from .pinned_github_png_transport import download_pinned_github_asset
except ImportError:
    from import_codex_pet import convert
    from install_native_role import validate_native_role
    from pinned_github_png_transport import download_pinned_github_asset

REVISION = "db2f6306ce78f6559ab27155d7bfaf00bf43809d"
REPO = "legeling/awesome-codex-pet"
ROOT = f"https://raw.githubusercontent.com/{REPO}/{REVISION}/pets"
MAX_FILE_BYTES = 5 * 1024 * 1024
# Git blob SHA-1 is the content address from the immutable source tree.
# The exact size and hash are both checked before any conversion.
SOURCES = {
    "citlali": ("citlali--zaytsevzy", "茜特菈莉", "genshin_citlali",
                (196, "e2e8c302092d606c68c76d6e011b371452a846d7"),
                (2149902, "0a89665f02a3fb804981d7406de07224b84b47ba")),
    "klee_desk": ("klee-desk--ayanxu56-boop", "可莉（书桌版）", "genshin_klee",
                  (259, "49c19327da5de592305cac89e91af6a99f9aca37"),
                  (2786608, "aa5e1852a8e822506ff59167367b8917f9b57639")),
    "paimon_companion": ("paimon-best-companion--makashibata", "派蒙（伙伴版）", "genshin_paimon",
                         (245, "6c9ec5dfd43671bcbfbaf057bdae65caaafec285"),
                         (2324392, "2a12d37f200008c8527ee8a85d9665053399bdec")),
    "furina": ("furina--lingxiaotian", "芙宁娜", "genshin_furina",
               (348, "b43626c1ba535dab702d95e590e3a970b0a6716b"),
               (1932404, "32db5ba1a20c6fca02476ecbfe5d746be0a5827b")),
    "hu_tao": ("hu-tao--lingxiaotian", "胡桃", "genshin_hu_tao",
               (284, "ea16c4107e51657c44c14d804bd26217aa392a87"),
               (2282724, "7a174a2b941dcc1599699836b25b2c2246b2d488")),
    "klee": ("klee--chenxin-dlut", "可莉", "genshin_klee",
             (225, "d97b4f7d111a009430cb08f8dc087f0516362eb9"),
             (2318174, "cecd1f439bbe39f949d770e89dec60e907a85d84")),
    "nahida": ("nahida--lingxiaotian", "纳西妲", "genshin_nahida",
               (257, "ae26cdbdc20add68c3df15764b69edb7477fd139"),
               (2496846, "1d0026bb60774174e158b5ff9ed0a3960774adba")),
    "paimon": ("paimon--lingxiaotian", "派蒙", "genshin_paimon",
               (215, "ea3947649e239bc5ef98a6e6be9f7b25090a431d"),
               (2150370, "d240ee030dac9a82498320aee164c009139a138f")),
    "raiden": ("raiden-shogun--lingxiaotian", "雷电将军", "genshin_raiden_shogun",
               (294, "a4d7fa0cbfe456b1bd0ea020128ce31d0b76aae4"),
               (2254702, "e92c4358f74938c4465047546a6010a7b020f70e")),
    "arlecchino": ("arlecchino--lingxiaotian", "阿蕾奇诺", "genshin_arlecchino",
                   (300, "f5b0044cedacf8eb2c602b7300196a8518f1264e"),
                   (2186692, "9b84ce534b2e10f1bd3f433ccf167d1aa33cdf51")),
    "ganyu": ("ganyu--chenxin-dlut", "甘雨", "genshin_ganyu",
              (196, "2ff047b60a9cb00eb1d371431d6aca6f068338d8"),
              (2121564, "85a2850375db028dc724e069d158e52c0d9833bb")),
    "ayaka": ("kamisato-ayaka--lingxiaotian", "神里绫华", "genshin_ayaka",
              (277, "35424a26388d9b537c771b967d13bd0fa03a8013"),
              (2300526, "bcc710697ef8ab8f104085d7c9dfbc3a8bb1b1f7")),
    "navia": ("navia--lingxiaotian", "娜维娅", "genshin_navia",
              (289, "ebac6141dd3be1ecdcf3b53eaf7a5c4dd2c17f1f"),
              (2607194, "1d34ebd0c1c4af8f30264f8125f4215011088539")),
    "yae_miko": ("yae-miko--legeling", "八重神子", "genshin_yae_miko",
                 (334, "8130a71e5b09885ee4b9ee01c2824ee0b8a11168"),
                 (3131636, "d71985759874924667c4fbe487c4596f06c1ed87")),
    "yoimiya": ("yoimiya--chenxin-dlut", "宵宫", "genshin_yoimiya",
                (271, "69c9e44a4cb4a8cc54cc6750af481053b9bbc619"),
                (1845034, "a97796903a44722d5573078ecfc5fe324f861a8d")),
}


def _download_pinned(url, expected, opener=urlopen):
    size, git_sha = expected
    if size > MAX_FILE_BYTES or size < 1:
        raise ValueError("Unsafe source file length")
    # Mirror only the SAME immutable original object; SHA and byte length
    # below remain mandatory regardless of which trusted host responds.
    data = download_pinned_github_asset(url, MAX_FILE_BYTES, opener=opener)
    if len(data) != size:
        raise ValueError("Downloaded art length differs from pinned source")
    if hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest() != git_sha:
        raise ValueError("Downloaded art differs from immutable Git source")
    return data


def install_artist_codex(kind, output_root, *, confirmed=False,
                         downloader=_download_pinned):
    if not confirmed:
        raise ValueError("Choose and confirm a personal character source first")
    if kind not in SOURCES:
        raise ValueError("Unsupported source character")
    pet_id, display, profile, manifest_spec, atlas_spec = SOURCES[kind]
    root = Path(output_root).expanduser()
    if root.is_symlink():
        raise ValueError("Refusing symbolic-link role root")
    root = root.resolve()
    folder = "SourceCodex" + "".join(piece.title() for piece in kind.split("_"))
    destination = root / folder
    if destination.exists() or destination.is_symlink():
        raise FileExistsError("This original-art role was already installed")
    root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=root, prefix=".codex-original-source-") as temp:
        src = Path(temp) / pet_id
        src.mkdir()
        base = f"{ROOT}/{pet_id}"
        for name, spec in (("pet.json", manifest_spec),
                           ("spritesheet.webp", atlas_spec)):
            (src / name).write_bytes(downloader(base + "/" + name, spec))
        manifest = json.loads((src / "pet.json").read_text(encoding="utf-8"))
        if manifest.get("id") != pet_id or manifest.get("spritesheetPath") != "spritesheet.webp":
            raise ValueError("Original source manifest does not match reviewed ID")
        # Only profiles with dedicated display configuration are passed to
        # the converter; other identities are bound in the import receipt.
        try:
            from .chibi_profiles import CHIBI_PROFILES
        except ImportError:
            from chibi_profiles import CHIBI_PROFILES
        converted = convert(src, root, folder=folder,
                            profile=profile if profile in CHIBI_PROFILES else None,
                            name=display, style="classic",
                            preserve_source_frames=True,
                            source_url=f"https://github.com/{REPO}/tree/{REVISION}/pets/{pet_id}",
                            license_name="See original artist submission; private install")
        result = validate_native_role(converted)
        (converted / "PERSONAL_IMPORT.json").write_text(
            json.dumps({"selected_profile": profile, "source_id": pet_id,
                        "display_name": display,
                        "source_repository": REPO, "source_commit": REVISION,
                        "source_kind": "curated_creator_spritesheet",
                        "source_rights_verified": False,
                        "likeness_manually_reviewed": False},
                       ensure_ascii=False, indent=2), encoding="utf-8")
    return {"folder": destination.name, "source": pet_id, "profile": profile,
            "actions": result["actions"], "frames": result["images"],
            "artist_sprites_retained": True, "visual_qa_pending": True}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("character", choices=tuple(SOURCES))
    parser.add_argument("--role-root", default="res/role")
    parser.add_argument("--accept-personal-use", action="store_true")
    args = parser.parse_args(argv)
    print(json.dumps(install_artist_codex(
        args.character, args.role_root,
        confirmed=args.accept_personal_use), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
