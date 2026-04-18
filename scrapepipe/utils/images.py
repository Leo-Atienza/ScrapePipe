import mimetypes
from pathlib import Path
from urllib.parse import urlparse

from scrapepipe.utils.filenames import sanitize_filename
from scrapepipe.utils.http import get_with_retry

_REQUEST_TIMEOUT = 20
_MAX_FILENAME_LEN = 60
_EXT_FALLBACK = ".jpg"
_CONTENT_TYPE_EXT = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/webp": ".webp",
}


class ImageDownloadError(Exception):
    pass


def download_images(
    urls: list[str],
    *,
    dest_dir: Path,
    slug: str,
    user_agent: str | None = None,
) -> list[tuple[str, Path]]:
    """Download each URL into ``dest_dir``; return (original_url, local_path) pairs.

    Failures are skipped — the original URL is kept out of the result so the
    Markdown writer falls back to the remote URL for that image.
    """
    if not urls:
        return []

    dest_dir.mkdir(parents=True, exist_ok=True)
    headers = {"User-Agent": user_agent} if user_agent else None

    saved: list[tuple[str, Path]] = []
    for idx, url in enumerate(urls, start=1):
        try:
            path = _download_one(url, dest_dir=dest_dir, slug=slug, index=idx, headers=headers)
        except Exception:
            continue
        saved.append((url, path))
    return saved


def _download_one(
    url: str,
    *,
    dest_dir: Path,
    slug: str,
    index: int,
    headers: dict | None,
) -> Path:
    response = get_with_retry(url, headers=headers, timeout=_REQUEST_TIMEOUT)
    if response.status_code >= 400:
        raise ImageDownloadError(f"HTTP {response.status_code} for {url}")

    ext = _infer_extension(url, response.headers.get("Content-Type", ""))
    base = sanitize_filename(f"{slug}_img{index:02d}", max_len=_MAX_FILENAME_LEN)
    path = dest_dir / f"{base}{ext}"
    path.write_bytes(response.content)
    return path


def _infer_extension(url: str, content_type: str) -> str:
    ctype = (content_type or "").split(";", 1)[0].strip().lower()
    if ctype in _CONTENT_TYPE_EXT:
        return _CONTENT_TYPE_EXT[ctype]
    if ctype:
        guessed = mimetypes.guess_extension(ctype)
        if guessed:
            return guessed

    path = urlparse(url).path.lower()
    for ext in (".jpg", ".jpeg", ".png", ".gif", ".webp"):
        if path.endswith(ext):
            return ".jpg" if ext == ".jpeg" else ext
    return _EXT_FALLBACK
