import os
from datetime import datetime, timezone
from urllib.parse import urlparse, urlunparse

import requests

from scrapepipe.extractors.base import Extractor
from scrapepipe.models import SocialPost

_DEFAULT_USER_AGENT = "ScrapePipe/0.1 (public-json fetcher)"
_REQUEST_TIMEOUT = 15


class RedditPostNotFound(Exception):
    pass


class RedditExtractor(Extractor):
    def __init__(self) -> None:
        self._user_agent = os.environ.get("REDDIT_USER_AGENT") or _DEFAULT_USER_AGENT

    def fetch(self, url: str) -> SocialPost:
        json_url = _as_json_url(url)
        response = requests.get(
            json_url,
            headers={"User-Agent": self._user_agent},
            timeout=_REQUEST_TIMEOUT,
            allow_redirects=True,
        )
        if response.status_code == 404:
            raise RedditPostNotFound(f"Post not found: {url}")
        response.raise_for_status()

        payload = response.json()
        post_data = _extract_post_data(payload)
        if post_data is None:
            raise RedditPostNotFound(f"No post data in response for: {url}")

        author = post_data.get("author") or "[deleted]"
        if author == "[deleted]" or post_data.get("removed_by_category"):
            author = "[deleted]"

        created_utc = post_data.get("created_utc")
        created_at = (
            datetime.fromtimestamp(created_utc, tz=timezone.utc)
            if created_utc is not None
            else datetime.now(timezone.utc)
        )

        permalink = post_data.get("permalink", "")
        canonical_url = (
            f"https://www.reddit.com{permalink}" if permalink else url
        )

        return SocialPost(
            platform="reddit",
            post_id=post_data.get("id", ""),
            author=author,
            author_handle=author if author != "[deleted]" else None,
            title=post_data.get("title"),
            content=post_data.get("selftext") or "",
            url=canonical_url,
            created_at=created_at,
            likes=post_data.get("score", 0),
            comments=post_data.get("num_comments", 0),
            image_urls=_extract_image_urls(post_data),
            raw={
                "id": post_data.get("id"),
                "subreddit": post_data.get("subreddit"),
                "over_18": post_data.get("over_18", False),
                "is_self": post_data.get("is_self", False),
            },
        )


def _as_json_url(url: str) -> str:
    parsed = urlparse(url)
    path = parsed.path.rstrip("/")
    if not path.endswith(".json"):
        path = f"{path}.json"
    return urlunparse(parsed._replace(path=path))


def _extract_post_data(payload) -> dict | None:
    if not isinstance(payload, list) or not payload:
        return None
    first_listing = payload[0]
    children = (first_listing.get("data") or {}).get("children") or []
    if not children:
        return None
    return children[0].get("data")


def _extract_image_urls(post_data: dict) -> list[str]:
    urls: list[str] = []

    direct_url = post_data.get("url_overridden_by_dest") or post_data.get("url", "")
    if direct_url and _looks_like_image(direct_url):
        urls.append(direct_url)

    gallery = post_data.get("media_metadata")
    if isinstance(gallery, dict):
        for item in gallery.values():
            if not isinstance(item, dict):
                continue
            source = item.get("s")
            if isinstance(source, dict) and source.get("u"):
                urls.append(source["u"].replace("&amp;", "&"))

    preview = post_data.get("preview")
    if isinstance(preview, dict):
        for image in preview.get("images", []):
            source = image.get("source", {})
            if source.get("url"):
                urls.append(source["url"].replace("&amp;", "&"))

    seen: set[str] = set()
    deduped: list[str] = []
    for u in urls:
        if u not in seen:
            seen.add(u)
            deduped.append(u)
    return deduped


_IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".gif", ".webp")


def _looks_like_image(url: str) -> bool:
    return url.lower().split("?", 1)[0].endswith(_IMAGE_EXTS)
