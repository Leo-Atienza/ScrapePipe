import html as html_lib
import re
import sys
from datetime import datetime, timezone

from scrapepipe.extractors.base import Extractor
from scrapepipe.models import SocialPost
from scrapepipe.utils.http import get_with_retry

_OEMBED_URL = "https://publish.twitter.com/oembed"
_REQUEST_TIMEOUT = 15

_TWEET_ID_RE = re.compile(r"(?:twitter|x)\.com/\w+/status/(\d+)", re.IGNORECASE)
_HANDLE_FROM_URL_RE = re.compile(
    r"(?:twitter|x)\.com/([A-Za-z0-9_]+)", re.IGNORECASE
)
_P_CONTENT_RE = re.compile(r"<p[^>]*>(.+?)</p>", re.DOTALL | re.IGNORECASE)
_A_TAG_RE = re.compile(
    r'<a[^>]+href="([^"]+)"[^>]*>([^<]*)</a>', re.IGNORECASE
)
_IMG_URL_RE = re.compile(
    r"https?://(?:pbs\.twimg\.com|pic\.twitter\.com)[^\s\"<>]+",
    re.IGNORECASE,
)
_TAG_RE = re.compile(r"<[^>]+>")
_BR_RE = re.compile(r"<br\s*/?>", re.IGNORECASE)


class TwitterPostNotFound(Exception):
    pass


def _log_retry(attempt: int, delay: float, status: int) -> None:
    print(
        f"  [retry] twitter returned {status}; sleeping {delay:.1f}s "
        f"(attempt {attempt}).",
        file=sys.stderr,
    )


class TwitterExtractor(Extractor):
    def fetch(self, url: str) -> SocialPost:
        tweet_id = extract_tweet_id(url)
        response = get_with_retry(
            _OEMBED_URL,
            params={"url": url, "omit_script": "1"},
            timeout=_REQUEST_TIMEOUT,
            on_retry=_log_retry,
        )
        if response.status_code in (403, 404):
            raise TwitterPostNotFound(
                f"Tweet not found, deleted, or from a protected account: {url}"
            )
        response.raise_for_status()

        payload = response.json()
        html_content = payload.get("html") or ""
        author_name = payload.get("author_name") or "[unknown]"
        canonical_url = payload.get("url") or url

        author_handle = _extract_handle(payload.get("author_url") or "")
        content = _extract_tweet_text(html_content)
        image_urls = _extract_image_urls(html_content)
        created_at = _extract_created_at(html_content)

        return SocialPost(
            platform="twitter",
            post_id=tweet_id,
            author=author_name,
            author_handle=author_handle,
            title=None,
            content=content,
            url=canonical_url,
            created_at=created_at,
            likes=0,
            comments=0,
            image_urls=image_urls,
            raw={"oembed": payload},
        )


def extract_tweet_id(url: str) -> str:
    match = _TWEET_ID_RE.search(url)
    if not match:
        raise ValueError(f"Could not extract tweet ID from URL: {url}")
    return match.group(1)


def _extract_handle(author_url: str) -> str | None:
    match = _HANDLE_FROM_URL_RE.search(author_url)
    return match.group(1) if match else None


def _extract_tweet_text(html_content: str) -> str:
    match = _P_CONTENT_RE.search(html_content)
    if not match:
        return ""
    inner = _BR_RE.sub("\n", match.group(1))
    stripped = _TAG_RE.sub("", inner)
    return html_lib.unescape(stripped).strip()


def _extract_image_urls(html_content: str) -> list[str]:
    found = _IMG_URL_RE.findall(html_content)
    seen: set[str] = set()
    deduped: list[str] = []
    for url in found:
        if url not in seen:
            seen.add(url)
            deduped.append(url)
    return deduped


def _extract_created_at(html_content: str) -> datetime:
    for _href, text in _A_TAG_RE.findall(html_content):
        candidate = html_lib.unescape(text).strip()
        for fmt in ("%B %d, %Y", "%b %d, %Y"):
            try:
                parsed = datetime.strptime(candidate, fmt)
                return parsed.replace(tzinfo=timezone.utc)
            except ValueError:
                continue
    return datetime.now(timezone.utc)
