"""Acquire a pinned FFmpeg decoder *only when* a local whale import needs it.

Windows portable applications deliberately do not bundle imageio-ffmpeg's
83 MiB executable twice. On first opt-in import we fetch the official pinned
PyPI wheel, check wheel SHA-256 and its FFmpeg member SHA-256, and atomically
cache only the executable beside this installation (not in Git or CI artifacts).
"""
from __future__ import annotations

import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import tempfile
from urllib.parse import urlparse
from urllib.request import urlopen
import zipfile

VERSION = "0.6.0"
WHEEL_NAME = "imageio_ffmpeg-0.6.0-py3-none-win_amd64.whl"
WHEEL_SHA256 = "02fa47c83703c37df6bfe4896aab339013f62bf02c5ebf2dce6da56af04ffc0a"
MEMBER_NAME = "imageio_ffmpeg/binaries/ffmpeg-win-x86_64-v7.1.exe"
BIN_SHA256 = "2ce797a0f88d7f067180338fb227f7b1928ea727bd9a4d7a1d022f7c52af71a3"
METADATA_URL = "https://pypi.org/pypi/imageio-ffmpeg/0.6.0/json"
WHEEL_DOWNLOAD_LIMIT = 36 * 1024 * 1024
BINARY_LIMIT = 100 * 1024 * 1024


def _sha_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for part in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(part)
    return h.hexdigest()


def _response_bytes(url: str, limit: int, *, opener) -> bytes:
    with opener(url, timeout=40) as response:
        final = response.geturl() if hasattr(response, "geturl") else url
        uri = urlparse(final)
        if uri.scheme != "https" or uri.hostname not in (
                "pypi.org", "files.pythonhosted.org"):
            raise ValueError("FFmpeg wheel metadata or binary redirected off trusted PyPI host")
        if uri.hostname == "pypi.org" and final != METADATA_URL:
            raise ValueError("PyPI metadata redirected unexpectedly")
        data = response.read(limit + 1)
    if len(data) > limit:
        raise ValueError("PyPI FFmpeg download exceeded size bound")
    return data


def fetch_pinned_windows_ffmpeg(cache: Path, *, opener=urlopen) -> str:
    """Use previously checked executable, else download a frozen PyPI wheel.

    Only one exact member can be extracted. Untrusted wheel files are never
    installed with pip or executed as Python. Cached files are not uploaded.
    """
    cache = Path(cache).expanduser()
    if cache.exists() and cache.is_symlink():
        raise ValueError("FFmpeg cache must not be a symlink")
    cache.mkdir(parents=True, exist_ok=True)
    target = cache / "ffmpeg-win-x86_64-v7.1.exe"
    if target.exists():
        if target.is_symlink() or not target.is_file() or _sha_file(target) != BIN_SHA256:
            raise ValueError("Cached FFmpeg has changed; refuse to execute it")
        return str(target.resolve())
    raw = _response_bytes(METADATA_URL, 1024 * 1024, opener=opener)
    metadata = json.loads(raw)
    wheels = [item for item in metadata.get("urls", [])
              if item.get("filename") == WHEEL_NAME]
    if len(wheels) != 1:
        raise ValueError("Pinned imageio-ffmpeg Windows wheel not present on PyPI")
    wheel = wheels[0]
    url = wheel.get("url", "")
    parsed = urlparse(url)
    if (parsed.scheme != "https" or parsed.hostname != "files.pythonhosted.org"
            or not parsed.path.endswith("/" + WHEEL_NAME)
            or wheel.get("digests", {}).get("sha256") != WHEEL_SHA256):
        raise ValueError("Pinned PyPI wheel identity mismatch")
    blob = _response_bytes(url, WHEEL_DOWNLOAD_LIMIT, opener=opener)
    if hashlib.sha256(blob).hexdigest() != WHEEL_SHA256:
        raise ValueError("Downloaded FFmpeg wheel SHA-256 mismatch")
    with zipfile.ZipFile(io.BytesIO(blob), "r") as archive:
        try:
            item = archive.getinfo(MEMBER_NAME)
        except KeyError as exc:
            raise ValueError("Pinned wheel contains no expected FFmpeg binary") from exc
        if not 0 < item.file_size <= BINARY_LIMIT:
            raise ValueError("Unexpected FFmpeg executable size")
        # The binary is extracted to a fresh temp file before a second SHA check.
        with tempfile.NamedTemporaryFile(dir=cache, prefix=".ffmpeg-",
                                         suffix=".tmp", delete=False) as temp:
            temp_name = Path(temp.name)
            try:
                digest = hashlib.sha256()
                with archive.open(item, "r") as stream:
                    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                        digest.update(chunk)
                        temp.write(chunk)
                temp.flush()
                if digest.hexdigest() != BIN_SHA256:
                    raise ValueError("FFmpeg executable SHA-256 mismatch")
            except BaseException:
                temp_name.unlink(missing_ok=True)
                raise
    if target.exists():
        temp_name.unlink(missing_ok=True)
        raise ValueError("Another FFmpeg appeared while installing")
    os.replace(str(temp_name), str(target))
    return str(target.resolve())


def locate_decoder(*, explicit: str | None = None, role_root: Path | None = None,
                   opener=urlopen) -> str:
    if explicit:
        file = Path(explicit).expanduser()
        if not file.is_file():
            raise ValueError("Specified FFmpeg executable does not exist")
        return str(file.resolve())
    # Source development can use an already installed imageio-ffmpeg runtime.
    # Deliberately no static import: the Windows frozen EXE must not embed it.
    try:
        import importlib
        imageio = importlib.import_module("imageio_ffmpeg")
        return imageio.get_ffmpeg_exe()
    except (ImportError, RuntimeError, OSError):
        pass
    system = shutil.which("ffmpeg")
    if system:
        return system
    if os.name != "nt":
        raise ValueError("FFmpeg not installed; install imageio-ffmpeg or ffmpeg first")
    if role_root is None:
        raise ValueError("Whale role directory required for on-demand FFmpeg")
    role_root = Path(role_root).resolve()
    # Keep binary in local installation data, separate from redistributable art.
    cache = role_root.parent.parent / "data" / "tools" / "whale_ffmpeg"
    return fetch_pinned_windows_ffmpeg(cache, opener=opener)
