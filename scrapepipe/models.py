from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class Comment:
    author: str
    body: str
    score: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    replies: list["Comment"] = field(default_factory=list)


@dataclass
class SocialPost:
    platform: str
    post_id: str
    author: str
    url: str
    content: str = ""
    author_handle: str | None = None
    title: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    likes: int = 0
    comments: int = 0
    image_urls: list[str] = field(default_factory=list)
    comments_tree: list[Comment] = field(default_factory=list)
    raw: dict = field(default_factory=dict)
