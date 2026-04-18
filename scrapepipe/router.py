import re
from urllib.parse import urlparse

from scrapepipe.extractors.base import Extractor


class UnsupportedPlatformError(ValueError):
    pass


_REDDIT_HOST_RE = re.compile(r"^(?:www\.|old\.|new\.)?reddit\.com$", re.IGNORECASE)
_TWITTER_HOST_RE = re.compile(r"^(?:www\.|mobile\.)?(?:twitter|x)\.com$", re.IGNORECASE)


def detect_platform(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    if _REDDIT_HOST_RE.match(host):
        return "reddit"
    if _TWITTER_HOST_RE.match(host):
        return "twitter"
    raise UnsupportedPlatformError(
        f"URL not supported (host: {host or '<none>'}). "
        "Supported: reddit.com, twitter.com, x.com."
    )


def route(url: str) -> Extractor:
    platform = detect_platform(url)
    if platform == "reddit":
        from scrapepipe.extractors.reddit import RedditExtractor
        return RedditExtractor()
    if platform == "twitter":
        from scrapepipe.extractors.twitter import TwitterExtractor
        return TwitterExtractor()
    raise UnsupportedPlatformError(f"No extractor for platform: {platform}")
