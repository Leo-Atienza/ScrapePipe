from pathlib import Path

from scrapepipe.models import Comment, SocialPost
from scrapepipe.utils.filenames import sanitize_filename
from scrapepipe.utils.images import download_images


def write_markdown(
    post: SocialPost,
    outdir: Path,
    *,
    download_images_enabled: bool = False,
    user_agent: str | None = None,
) -> Path:
    outdir.mkdir(parents=True, exist_ok=True)

    date_part = post.created_at.strftime("%Y-%m-%d")
    author_part = sanitize_filename(post.author, max_len=40)
    id_part = sanitize_filename(post.post_id, max_len=20)
    slug = f"{post.platform}_{date_part}_{author_part}_{id_part}"
    path = outdir / f"{slug}.md"

    image_map: dict[str, str] = {}
    if download_images_enabled and post.image_urls:
        images_dir = outdir / f"{slug}_images"
        saved = download_images(
            post.image_urls,
            dest_dir=images_dir,
            slug=slug,
            user_agent=user_agent,
        )
        for original_url, local_path in saved:
            image_map[original_url] = f"{images_dir.name}/{local_path.name}"

    path.write_text(render(post, image_map=image_map), encoding="utf-8")
    return path


def render(post: SocialPost, *, image_map: dict[str, str] | None = None) -> str:
    image_map = image_map or {}
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
            rendered = image_map.get(image_url, image_url)
            lines.append(f"![]({rendered})")

    if post.comments_tree:
        lines.append("")
        lines.append("---")
        lines.append("")
        total_top_level = len(post.comments_tree)
        lines.append(f"## Comments ({total_top_level} top-level shown of {post.comments} total)")
        lines.append("")
        for comment in post.comments_tree:
            lines.extend(_render_comment(comment, depth=0))
            lines.append("")

    lines.append("")
    return "\n".join(lines)


def _render_comment(comment: Comment, *, depth: int) -> list[str]:
    prefix = "> " * depth
    header = f"{prefix}**u/{comment.author}** \u00b7 \u2191 {comment.score} \u00b7 {comment.created_at.isoformat()}"
    body_lines = (comment.body or "").splitlines() or [""]
    rendered = [header, f"{prefix}"]
    for body_line in body_lines:
        rendered.append(f"{prefix}{body_line}")

    for reply in comment.replies:
        rendered.append(f"{prefix}")
        rendered.extend(_render_comment(reply, depth=depth + 1))

    return rendered


def _first_line(text: str, max_len: int = 80) -> str:
    if not text:
        return ""
    first = text.strip().splitlines()[0] if text.strip() else ""
    return first[:max_len]
