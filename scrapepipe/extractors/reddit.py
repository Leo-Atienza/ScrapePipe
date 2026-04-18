import os
import sys
from datetime import datetime, timezone
from urllib.parse import urlencode, urlparse, urlunparse

import requests

from scrapepipe.extractors.base import Extractor
from scrapepipe.models import Comment, SocialPost
from scrapepipe.utils.http import get_with_retry

_DEFAULT_USER_AGENT = "ScrapePipe/0.1 (public-json fetcher)"
_REQUEST_TIMEOUT = 15
_SEARCH_URL = "https://www.reddit.com/search.json"
_VALID_SORTS = {"relevance", "top", "new", "hot", "comments"}
_IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".gif", ".webp")


class RedditPostNotFound(Exception):
    pass


def _log_retry(attempt: int, delay: float, status: int) -> None:
    print(
        f"  [retry] reddit returned {status}; sleeping {delay:.1f}s "
        f"(attempt {attempt}).",
        file=sys.stderr,
    )


class RedditExtractor(Extractor):
    def __init__(self) -> None:
        self._user_agent = os.environ.get("REDDIT_USER_AGENT") or _DEFAULT_USER_AGENT

    def fetch(self, url: str) -> SocialPost:
        json_url = _as_json_url(url)
        response = self._get(json_url)
        if response.status_code == 404:
            raise RedditPostNotFound(f"Post not found: {url}")
        response.raise_for_status()

        payload = response.json()
        post_data = _first_post_from_listing(payload)
        if post_data is None:
            raise RedditPostNotFound(f"No post data in response for: {url}")

        comments_listing = payload[1] if isinstance(payload, list) and len(payload) > 1 else None
        comments_tree = _parse_comments_listing(comments_listing) if comments_listing else []

        post = build_post(post_data, fallback_url=url)
        post.comments_tree = comments_tree
        return post

    def search(
        self,
        query: str,
        limit: int = 10,
        sort: str = "relevance",
    ) -> list[SocialPost]:
        if sort not in _VALID_SORTS:
            raise ValueError(
                f"Invalid sort '{sort}'. Choose from: {sorted(_VALID_SORTS)}"
            )
        params = {
            "q": query,
            "limit": str(max(1, min(limit, 100))),
            "sort": sort,
            "type": "link",
        }
        url = f"{_SEARCH_URL}?{urlencode(params)}"
        response = self._get(url)
        response.raise_for_status()
        payload = response.json()

        children = (payload.get("data") or {}).get("children") or []
        posts: list[SocialPost] = []
        for child in children:
            post_data = child.get("data") or {}
            permalink = post_data.get("permalink", "")
            fallback = (
                f"https://www.reddit.com{permalink}" if permalink else ""
            )
            posts.append(build_post(post_data, fallback_url=fallback))
        return posts

    def _get(self, url: str) -> requests.Response:
        return get_with_retry(
            url,
            headers={"User-Agent": self._user_agent},
            timeout=_REQUEST_TIMEOUT,
            on_retry=_log_retry,
        )


def build_post(post_data: dict, *, fallback_url: str = "") -> SocialPost:
    author = post_data.get("author") or "[deleted]"
    if post_data.get("removed_by_category"):
        author = "[deleted]"

    created_utc = post_data.get("created_utc")
    created_at = (
        datetime.fromtimestamp(created_utc, tz=timezone.utc)
        if created_utc is not None
        else datetime.now(timezone.utc)
    )

    permalink = post_data.get("permalink", "")
    canonical_url = (
        f"https://www.reddit.com{permalink}" if permalink else fallback_url
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


def _first_post_from_listing(payload) -> dict | None:
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


def _looks_like_image(url: str) -> bool:
    return url.lower().split("?", 1)[0].endswith(_IMAGE_EXTS)


def _parse_comments_listing(listing: dict | None) -> list[Comment]:
    if not isinstance(listing, dict):
        return []
    data = listing.get("data") or {}
    children = data.get("children") or []
    result: list[Comment] = []
    for child in children:
        if not isinstance(child, dict):
            continue
        if child.get("kind") != "t1":
            # Skip "more" placeholders and non-comment entries.
            continue
        comment_data = child.get("data") or {}
        result.append(_build_comment(comment_data))
    return result


def _build_comment(data: dict) -> Comment:
    author = data.get("author") or "[deleted]"
    body = data.get("body")
    if body is None or data.get("removed_by_category"):
        body = "[removed]"

    created_utc = data.get("created_utc")
    created_at = (
        datetime.fromtimestamp(created_utc, tz=timezone.utc)
        if created_utc is not None
        else datetime.now(timezone.utc)
    )

    replies_field = data.get("replies")
    replies: list[Comment] = []
    if isinstance(replies_field, dict):
        replies = _parse_comments_listing(replies_field)

    return Comment(
        author=author,
        body=body,
        score=data.get("score", 0),
        created_at=created_at,
        replies=replies,
    )
