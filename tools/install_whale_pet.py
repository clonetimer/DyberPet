#!/usr/bin/env python3
"""Opt-in local installation of the real dsh-whale-pet transparent WebM art.

No video or extracted PNG is stored in git or hosted CI artifacts. The original
upstream WebM bytes are checked against a fixed Git commit/blob and converted
on the user's own computer to native DyberPet PNG-sequence actions.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from urllib.parse import urlparse
from urllib.request import urlopen

from PIL import Image
from tools.chibi_profiles import available_role_folder
from tools.install_native_role import validate_native_role

CATALOG = Path(__file__).with_name("whale_creator_sources.json")
SOURCE_REPO = "luweiyabo/dsh-whale-pet"
SOURCE_REV = "b61b445e6be05a732fc6738b825240aeffdf6769"
SOURCE_ROOT = f"https://raw.githubusercontent.com/{SOURCE_REPO}/{SOURCE_REV}"
ROLE_NAME = "SourceWhalePet"
# These are truly authored source clips, not a newly drawn generic whale.
CORE_ACTIONS = (
    "idle/breathing", "turn/looking_around", "moves/floating_steps",
    "moves/target_point_run", "clicks/arrival_wave",
    "clicks/cheerful_wave", "clicks/happy_hop",
    "drag/dragged_in_midair", "drag/turn_into_ball",
    "daily/attentive_listening", "daily/quick_nap",
    "work/coding", "work/deep_thought",
    "special/whale_bubbles", "special/whale_tail_slap",
    "special/blue_whale_appears",
)
# Keep conversion bounded; full mode deliberately samples less frequently.
MAX_VIDEO_BYTES = 2 * 1024 * 1024
MAX_PNG_FRAMES = 6000
MAX_FRAME_BYTES = 4 * 1024 * 1024


def source_catalog() -> dict:
    result = json.loads(CATALOG.read_text(encoding="utf-8"))
    if (result.get("source_repository") != SOURCE_REPO
            or result.get("source_commit") != SOURCE_REV
            or result.get("animation_count") != 95):
        raise ValueError("Whale source catalog changed unexpectedly")
    entries = result.get("animations")
    if not isinstance(entries, list) or len(entries) != 95:
        raise ValueError("Incomplete pinned whale animation catalog")
    paths = set()
    for row in entries:
        if not isinstance(row, dict):
            raise ValueError("Malformed whale catalog row")
        name = row.get("path")
        if (not isinstance(name, str) or
                not re.fullmatch(r"assets/thumb/[a-z]+/[a-z][a-z0-9_]*\.webm", name)
                or name in paths):
            raise ValueError("Unsafe or repeated whale source path")
        paths.add(name)
        if type(row.get("size")) is not int or not 0 < row["size"] <= MAX_VIDEO_BYTES:
            raise ValueError("Unsafe whale source byte length")
        if not re.fullmatch(r"[0-9a-f]{40}", str(row.get("git_blob_sha1", ""))):
            raise ValueError("Missing exact upstream Git blob SHA")
    if set("assets/thumb/" + n + ".webm" for n in CORE_ACTIONS) - paths:
        raise ValueError("Core whale actions are not in pinned source catalog")
    return result


def select_actions(catalog: dict, selection: str) -> list[dict]:
    if selection not in ("core", "full"):
        raise ValueError("Only core or full animation profiles supported")
    mapping = {row["path"]: row for row in catalog["animations"]}
    if selection == "full":
        return [mapping[name] for name in sorted(mapping)]
    return [mapping["assets/thumb/" + name + ".webm"] for name in CORE_ACTIONS]


def _git_blob_sha(data: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\x00" + data).hexdigest()


def fetch_pinned_video(row: dict, *, opener=urlopen) -> bytes:
    """No arbitrary URLs; fixed commit/path/size/blob, fail on unsafe redirects."""
    name = row["path"]
    if not re.fullmatch(r"assets/thumb/[a-z]+/[a-z][a-z0-9_]*\.webm", name):
        raise ValueError("Untrusted whale source path")
    expected = row["size"]
    if type(expected) is not int or not 0 < expected <= MAX_VIDEO_BYTES:
        raise ValueError("Invalid pinned source size")
    url = SOURCE_ROOT + "/" + name
    with opener(url, timeout=30) as response:
        final_url = response.geturl() if hasattr(response, "geturl") else url
        url_info = urlparse(final_url)
        if (url_info.scheme != "https" or url_info.hostname != "raw.githubusercontent.com"
                or url_info.path != urlparse(url).path):
            raise ValueError("Unsafe upstream media redirect")
        data = response.read(MAX_VIDEO_BYTES + 1)
    if len(data) != expected or _git_blob_sha(data) != row["git_blob_sha1"]:
        raise ValueError("Whale video source bytes differ from pinned upstream Git blob")
    return data


def locate_ffmpeg(explicit=None) -> str:
    if explicit:
        exe = Path(explicit).expanduser()
        if not exe.is_file():
            raise ValueError("Selected FFmpeg executable does not exist")
        return str(exe.resolve())
    # imageio-ffmpeg supplies a Windows binary in source/dev and frozen builds.
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except (ImportError, RuntimeError, OSError):
        found = shutil.which("ffmpeg")
        if found:
            return found
        raise ValueError("FFmpeg decoder missing; install imageio-ffmpeg or provide --ffmpeg")


def decode_video(clip: Path, target: Path, *, ffmpeg: str, fps: int) -> int:
    """Preserve actual frames and alpha; never draw/replace author images."""
    if fps not in (5, 8):
        raise ValueError("Whale decoder FPS must be 5 or 8")
    target.mkdir(parents=True, exist_ok=True)
    # libvpx-vp9 (not default native VP9) is required for WebM alpha decoding.
    args = [ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
            "-c:v", "libvpx-vp9", "-i", str(clip), "-an",
            "-vf", f"fps={fps},scale=320:180:flags=lanczos,format=rgba",
            "-frames:v", str(10 * fps), "-start_number", "0",
            str(target / "frame_%d.png")]
    try:
        proc = subprocess.run(args, capture_output=True, text=True,
                              timeout=120, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ValueError("Whale video decoding failed or exceeded time limit") from exc
    if proc.returncode:
        raise ValueError("FFmpeg alpha/video decoder failed: " + proc.stderr[-320:])
    frames = sorted(target.glob("frame_*.png"),
                    key=lambda x: int(x.stem.split("_")[-1]))
    if not 2 <= len(frames) <= 10 * fps:
        raise ValueError("Decoded whale animation has insufficient/excessive real frames")
    if [int(p.stem.split("_")[-1]) for p in frames] != list(range(len(frames))):
        raise ValueError("Whale animation numbered frame gap")
    has_transparency = False
    has_visible_pixels = False
    for frame in frames:
        if frame.is_symlink() or frame.stat().st_size > MAX_FRAME_BYTES:
            raise ValueError("Invalid decoded animation frame")
        with Image.open(frame) as im:
            im.load()
            if im.size != (320, 180) or im.mode != "RGBA":
                raise ValueError("Whale animation lost RGBA geometry")
            alpha = im.getchannel("A")
            has_transparency |= alpha.getextrema()[0] < 255
            has_visible_pixels |= alpha.getbbox() is not None
    if not (has_transparency and has_visible_pixels):
        raise ValueError("Whale source transparency missing; refusing opaque substitution")
    return len(frames)


def write_native_configs(folder: Path, animations: list[dict], counts: dict,
                         *, fps: int) -> None:
    actions = {}
    for row in animations:
        name = Path(row["path"]).stem
        actions[name] = {
            "images": name, "act_num": 1, "frame_refresh": 1.0 / fps,
        }
    def use(key, fallback="breathing"):
        return key if key in actions else fallback
    basics = [
        ("待机呼吸", "breathing", 1.0),
        ("东张西望", "looking_around", 0.16),
        ("悬浮踏步", "floating_steps", 0.10),
        ("挥手打招呼", "arrival_wave", 0.15),
        ("开心挥手", "cheerful_wave", 0.10),
        ("开心跃动", "happy_hop", 0.08),
        ("认真倾听", "attentive_listening", 0.07),
        ("休息小憩", "quick_nap", 0.05),
        ("编程", "coding", 0.07),
        ("深度思考", "deep_thought", 0.07),
        ("鲸鱼吐泡泡", "whale_bubbles", 0.12),
        ("鲸鱼摆尾", "whale_tail_slap", 0.07),
        ("蓝鲸登场", "blue_whale_appears", 0.04),
    ]
    random_act = [
        {"name": title, "act_list": [action], "act_prob": probability,
         "act_type": [2, 0]}
        for title, action, probability in basics if action in actions
    ]
    random_act.append({
        "name": "onfloor", "act_list": [use("breathing")],
        "act_prob": 0, "act_type": [0, 10000],
    })
    pet = {
        "width": 320, "height": 180, "scale": 1.0,
        "interact_speed": 0.02, "default": "breathing",
        "up": "breathing", "down": "breathing",
        "left": use("floating_steps"), "right": use("floating_steps"),
        "drag": use("dragged_in_midair"), "prefall": use("turn_into_ball"),
        "fall": use("turn_into_ball"), "on_floor": "breathing",
        "focus": use("coding"), "random_act": random_act,
    }
    (folder / "act_conf.json").write_text(
        json.dumps(actions, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (folder / "pet_conf.json").write_text(
        json.dumps(pet, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    info_dir = folder / "info"
    info_dir.mkdir()
    # Produce the role picker portrait using real author PNG pixels only,
    # never a synthetic/mismatched mascot or an unknown default icon.
    import shutil as _shutil
    _shutil.copyfile(folder / "action" / "breathing_0.png", info_dir / "cover.png")
    chosen = None
    for i in range(min(counts.get("breathing", 1), 8)):
        with Image.open(folder / "action" / f"breathing_{i}.png") as frame:
            rgba = frame.convert("RGBA")
            bbox = rgba.getchannel("A").getbbox()
            if bbox is not None:
                chosen = rgba.crop(bbox)
                break
    if chosen is not None:
        chosen.thumbnail((176, 176), Image.Resampling.LANCZOS)
        icon = Image.new("RGBA", (192, 192), (0, 0, 0, 0))
        icon.alpha_composite(chosen, ((192 - chosen.width) // 2,
                                      (192 - chosen.height) // 2))
        icon.save(info_dir / "pfp.png")
    (info_dir / "info.json").write_text(json.dumps({
        "petName": "鲸鱼娘 Whale Pet",
        "coverImages": ["cover.png"],
        "pfp": "pfp.png" if chosen is not None else None,
        "tages": {"WebM 原作者动画": "#81C7DD", "个人非商用": "#AAC6D0"},
        "intro": ("由 luweiyabo/dsh-whale-pet 固定版本视频转换；"
                  "不含 DeepSeek Harness 工作状态侦测；素材分项许可见 SOURCE_LICENSE.txt。"),
        "author": {"name": "luweiyabo / PC2005-cloud contributors",
                   "infos": "Upstream asset authors; not a grant for commercial redistribution"},
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def install_whale_pet(output_root: Path, *, confirmed: bool = False,
                      selection: str = "core", ffmpeg: str | None = None,
                      opener=None, decoder=decode_video) -> dict:
    """Only a deliberate local opt-in creates a role; never overwrite originals."""
    if not confirmed:
        raise ValueError("Whale animation license acknowledgement required")
    catalog = source_catalog()
    entries = select_actions(catalog, selection)
    fps = 8 if selection == "core" else 5
    binary = locate_ffmpeg(ffmpeg)
    root = Path(output_root).expanduser()
    if root.is_symlink() or (root.exists() and not root.is_dir()):
        raise ValueError("Role root must not be a symlink")
    root = root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    folder_name = available_role_folder(root, ROLE_NAME)
    dest = root / folder_name
    if dest.exists() or dest.is_symlink():
        raise FileExistsError("Refusing to overwrite an existing whale role")
    with tempfile.TemporaryDirectory(dir=root, prefix=".whale-local-") as tempdir:
        temp = Path(tempdir)
        stage = temp / folder_name
        stage.mkdir()
        action_root = stage / "action"
        action_root.mkdir()
        counts = {}
        for row in entries:
            name = Path(row["path"]).stem
            if name in counts:
                raise ValueError("Duplicate whale animation ID")
            clip = temp / (name + ".webm")
            blob = fetch_pinned_video(row, opener=opener) if opener else fetch_pinned_video(row)
            clip.write_bytes(blob)
            raw = temp / ("frames_" + name)
            count = decoder(clip, raw, ffmpeg=binary, fps=fps)
            if not 2 <= count <= 10 * fps:
                raise ValueError("Invalid decoded frame count")
            for i in range(count):
                src = raw / f"frame_{i}.png"
                if not src.is_file() or src.is_symlink():
                    raise ValueError("Decoder did not produce all frames")
                src.rename(action_root / f"{name}_{i}.png")
            counts[name] = count
            shutil.rmtree(raw)
            clip.unlink()
            if sum(counts.values()) > MAX_PNG_FRAMES:
                raise ValueError("Whale frame budget exceeded")
        write_native_configs(stage, entries, counts, fps=fps)
        validated = validate_native_role(stage)
        if validated["actions"] != len(entries):
            raise ValueError("Whale native actions missing after conversion")
        (stage / "SOURCE_LICENSE.txt").write_text(
            "Upstream: https://github.com/luweiyabo/dsh-whale-pet\n"
            f"Fixed source commit: {SOURCE_REV}\n"
            "Source media rights are NOT covered by the MIT source-code license.\n"
            "Many assets originate from PC2005-cloud/dsh-pet: open source usage,\n"
            "non-commercial only; confirm the original authors' terms.\n"
            "https://github.com/luweiyabo/dsh-whale-pet/blob/main/THIRD_PARTY_ASSETS.md\n"
            "This local conversion does not include upstream JS/DeepSeek Harness integration.\n",
            encoding="utf-8")
        (stage / "PERSONAL_IMPORT.json").write_text(json.dumps({
            "display_name": "鲸鱼娘 Whale Pet",
            "source_id": "dsh_whale_pet",
            "source_repository": SOURCE_REPO, "source_commit": SOURCE_REV,
            "source_kind": "original_pinned_webm_converted_to_native_png",
            "selection": selection, "fps": fps,
            "original_art_replaced": False, "local_only": True,
            "source_rights_verified": False, "physical_desktop_qa_verified": False,
            "voice_included": False, "harness_event_hooks_included": False,
            "animations": counts,
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        if dest.exists() or dest.is_symlink():
            raise FileExistsError("Whale role appeared during conversion")
        stage.rename(dest)
    return {"folder": folder_name, "actions": len(entries),
            "frames": sum(counts.values()), "source_commit": SOURCE_REV,
            "selection": selection, "built_into_public_release": False,
            "requires_desktop_review": True}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path,
                        default=Path(__file__).resolve().parents[1] / "res/role")
    parser.add_argument("--selection", choices=("core", "full"), default="core")
    parser.add_argument("--ffmpeg", help="Optional local FFmpeg path; bundled decoder preferred")
    parser.add_argument("--accept-noncommercial-source-terms", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = install_whale_pet(
            args.output_root, selection=args.selection, confirmed=args.accept_noncommercial_source_terms,
            ffmpeg=args.ffmpeg)
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        parser.exit(2, "Whale installation failed: " + str(exc) + "\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
