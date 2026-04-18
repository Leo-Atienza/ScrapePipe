"""Streamlit GUI for ScrapePipe.

Run with: streamlit run app.py
"""
import os
import time
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from scrapepipe.extractors.reddit import RedditExtractor, RedditPostNotFound
from scrapepipe.extractors.twitter import TwitterPostNotFound
from scrapepipe.router import UnsupportedPlatformError, route
from scrapepipe.utils.http import RateLimitedError
from scrapepipe.writers.markdown import write_markdown

load_dotenv()

st.set_page_config(page_title="ScrapePipe", page_icon="📥", layout="wide")

st.title("📥 ScrapePipe")
st.caption("Fetch Reddit and X/Twitter posts as LLM-ready Markdown.")

with st.sidebar:
    st.header("Output settings")
    outdir_input = st.text_input("Output directory", value="./downloads")
    download_images = st.checkbox(
        "Download images locally",
        value=False,
        help="Save each image next to the .md file instead of linking remote URLs.",
    )
    delay = st.number_input(
        "Delay between requests (seconds)",
        min_value=0.0,
        max_value=30.0,
        value=1.0,
        step=0.5,
        help="Used by batch fetch and search.",
    )
    st.divider()
    st.caption(
        "Rate-limit auto-retry is always on (exponential backoff, respects "
        "`Retry-After`)."
    )

tab_fetch, tab_many, tab_search = st.tabs(
    ["Fetch one", "Fetch many", "Search Reddit"]
)


def _user_agent() -> str | None:
    return os.environ.get("REDDIT_USER_AGENT")


def _save_post(url: str, outdir: Path) -> tuple[bool, str, Path | None]:
    try:
        extractor = route(url)
        post = extractor.fetch(url)
        path = write_markdown(
            post,
            outdir,
            download_images_enabled=download_images,
            user_agent=_user_agent(),
        )
        return True, f"Saved: {path.name}", path
    except UnsupportedPlatformError as e:
        return False, f"Unsupported URL: {e}", None
    except (RedditPostNotFound, TwitterPostNotFound) as e:
        return False, f"Not found: {e}", None
    except RateLimitedError as e:
        return False, f"Rate-limited: {e}", None
    except Exception as e:
        return False, f"Error: {e}", None


def _render_result(path: Path) -> None:
    content = path.read_text(encoding="utf-8")
    st.success(f"Saved to `{path}`")
    col_dl, col_preview = st.columns([1, 3])
    with col_dl:
        st.download_button(
            "Download .md",
            data=content,
            file_name=path.name,
            mime="text/markdown",
        )
    with col_preview:
        with st.expander("Preview Markdown", expanded=True):
            st.markdown(content)


with tab_fetch:
    st.subheader("Fetch a single post")
    url = st.text_input(
        "Post URL",
        placeholder="https://www.reddit.com/r/python/comments/...  or  https://x.com/user/status/...",
        key="single_url",
    )
    if st.button("Fetch", type="primary", key="fetch_single"):
        if not url.strip():
            st.error("Paste a URL first.")
        else:
            outdir = Path(outdir_input)
            with st.spinner("Fetching..."):
                ok, msg, path = _save_post(url.strip(), outdir)
            if ok and path is not None:
                _render_result(path)
            else:
                st.error(msg)


with tab_many:
    st.subheader("Fetch many posts")
    st.caption("One URL per line. Blank lines and `#` comments are skipped.")
    bulk_text = st.text_area(
        "URLs",
        height=180,
        placeholder="https://www.reddit.com/r/python/comments/...\nhttps://x.com/user/status/...",
        key="many_urls",
    )
    if st.button("Fetch all", type="primary", key="fetch_many"):
        urls = [
            line.strip()
            for line in bulk_text.splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
        # de-dupe, preserve order
        seen: set[str] = set()
        urls = [u for u in urls if not (u in seen or seen.add(u))]

        if not urls:
            st.error("No URLs to fetch.")
        else:
            outdir = Path(outdir_input)
            progress = st.progress(0.0, text="Starting...")
            log_area = st.empty()
            logs: list[str] = []
            saved_paths: list[Path] = []
            succeeded = failed = 0

            for i, u in enumerate(urls, start=1):
                progress.progress(
                    (i - 1) / len(urls), text=f"[{i}/{len(urls)}] {u}"
                )
                ok, msg, path = _save_post(u, outdir)
                if ok and path is not None:
                    succeeded += 1
                    saved_paths.append(path)
                    logs.append(f"✅ [{i}/{len(urls)}] {msg}")
                else:
                    failed += 1
                    logs.append(f"❌ [{i}/{len(urls)}] {u} — {msg}")
                log_area.code("\n".join(logs))
                if i < len(urls) and delay > 0:
                    time.sleep(delay)

            progress.progress(1.0, text="Done.")
            st.success(f"Done: {succeeded} succeeded, {failed} failed.")
            if saved_paths:
                with st.expander(f"View {len(saved_paths)} saved file(s)"):
                    for p in saved_paths:
                        st.markdown(f"- `{p}`")


with tab_search:
    st.subheader("Search Reddit by topic")
    st.caption("X/Twitter search requires paid API access — not supported here.")
    query = st.text_input("Query", placeholder="python dataclass", key="search_q")
    col1, col2 = st.columns(2)
    with col1:
        limit = st.number_input("Limit", min_value=1, max_value=100, value=10)
    with col2:
        sort = st.selectbox(
            "Sort",
            ["relevance", "top", "new", "hot", "comments"],
            index=0,
        )
    if st.button("Search", type="primary", key="search_btn"):
        if not query.strip():
            st.error("Enter a query first.")
        else:
            outdir = Path(outdir_input)
            with st.spinner("Searching Reddit..."):
                try:
                    posts = RedditExtractor().search(
                        query.strip(), limit=int(limit), sort=sort
                    )
                except RateLimitedError as e:
                    st.error(f"Rate-limited: {e}")
                    posts = []
                except Exception as e:
                    st.error(f"Search failed: {e}")
                    posts = []

            if posts:
                st.info(f"Found {len(posts)} post(s). Saving to `{outdir}`...")
                progress = st.progress(0.0)
                saved_paths: list[Path] = []
                ua = _user_agent()
                for i, post in enumerate(posts, start=1):
                    try:
                        path = write_markdown(
                            post,
                            outdir,
                            download_images_enabled=download_images,
                            user_agent=ua,
                        )
                        saved_paths.append(path)
                    except Exception as e:
                        st.warning(f"Failed to write post {post.post_id}: {e}")
                    progress.progress(i / len(posts))

                st.success(f"Saved {len(saved_paths)} post(s).")
                with st.expander(f"View {len(saved_paths)} saved file(s)"):
                    for p in saved_paths:
                        st.markdown(f"- `{p}`")
            elif query.strip():
                st.warning("No results.")
