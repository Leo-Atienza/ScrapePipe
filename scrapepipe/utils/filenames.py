import re
import unicodedata

_ILLEGAL_CHARS_RE = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_WHITESPACE_RE = re.compile(r"\s+")


def sanitize_filename(name: str, max_len: int = 80) -> str:
    if not name:
        return "untitled"

    normalized = unicodedata.normalize("NFKD", name)
    ascii_only = normalized.encode("ascii", "ignore").decode("ascii")
    cleaned = _ILLEGAL_CHARS_RE.sub("", ascii_only)
    cleaned = _WHITESPACE_RE.sub("_", cleaned).strip("._")

    if not cleaned:
        return "untitled"
    return cleaned[:max_len]
