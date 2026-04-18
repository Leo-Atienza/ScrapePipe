from pathlib import Path

from scrapepipe.models import SocialPost
from scrapepipe.utils.filenames import sanitize_filename


def write_markdown(post: SocialPost, outdir: Path) -> Path:
    outdir.mkdir(parents=True, exist_ok=True)

    date_part = post.created_at.strftime("%Y-%m-%d")
    author_part = sanitize_filename(post.author, max_len=40)
    id_part = sanitize_filename(post.post_id, max_len=20)
    filename = f"{post.platform}_{date_part}_{author_part}_{id_part}.md"
    path = outdir / filename

    path.write_text(render(post), encoding="utf-8")
    return path


def render(post: SocialPost) -> str:
    heading = post.title or _first_line(post.content) or f"{post.platform} post {post.post_id}"
    handle_suffix = f" (@{post.author_handle})" if post.author_handle else ""

    lines = [
        f"# {heading}",
        "",
        f"**Author:** {post.author}{handle_suffix}",
        f"**Platform:** {post.platform}",
        f"**Posted:** {post.created_at.isoformat()}",
        f"**URL:** {post.url}",
        f"**Likes:** {post.likes} \u2022 **Comments:** {post.comments}",
        "",
        "---",
        "",
        post.content.strip() or "_(no text content)_",
    ]

    if post.image_urls:
        lines.append("")
        for image_url in post.image_urls:
            lines.append(f"![]({image_url})")

    lines.append("")
    return "\n".join(lines)


def _first_line(text: str, max_len: int = 80) -> str:
    if not text:
        return ""
    first = text.strip().splitlines()[0] if text.strip() else ""
    return first[:max_len]
