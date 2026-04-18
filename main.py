import argparse
import sys
import time
import traceback
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="scrapepipe",
        description="Fetch social media posts and save them as Markdown.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    fetch_parser = subparsers.add_parser("fetch", help="Fetch one post by URL.")
    fetch_parser.add_argument("url", help="Post URL (Reddit or X/Twitter).")
    _add_common_args(fetch_parser)

    many_parser = subparsers.add_parser(
        "fetch-many",
        help="Fetch multiple posts from positional URLs or a file.",
    )
    many_parser.add_argument(
        "urls",
        nargs="*",
        help="Post URLs. Omit if using --file.",
    )
    many_parser.add_argument(
        "--file",
        dest="url_file",
        help="Path to a file with one URL per line (# comments allowed).",
    )
    many_parser.add_argument(
        "--delay",
        type=float,
        default=1.0,
        help="Seconds to wait between fetches (default: 1.0).",
    )
    _add_common_args(many_parser)

    search_parser = subparsers.add_parser(
        "search",
        help="Search Reddit by query and save matching posts.",
    )
    search_parser.add_argument("query", help="Search query (Reddit only in v1).")
    search_parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Max posts to fetch (default: 10, max: 100).",
    )
    search_parser.add_argument(
        "--sort",
        default="relevance",
        choices=["relevance", "top", "new", "hot", "comments"],
        help="Sort order (default: relevance).",
    )
    _add_common_args(search_parser)

    args = parser.parse_args(argv)

    if args.command == "fetch":
        return _run_fetch(args.url, Path(args.outdir), verbose=args.verbose)
    if args.command == "fetch-many":
        urls = _collect_urls(args.urls, args.url_file)
        if not urls:
            print("Error: no URLs given. Pass URLs as args or use --file.", file=sys.stderr)
            return 2
        return _run_fetch_many(
            urls, Path(args.outdir), delay=args.delay, verbose=args.verbose
        )
    if args.command == "search":
        return _run_search(
            args.query,
            limit=args.limit,
            sort=args.sort,
            outdir=Path(args.outdir),
            verbose=args.verbose,
        )

    parser.print_help()
    return 1


def _add_common_args(subparser: argparse.ArgumentParser) -> None:
    subparser.add_argument(
        "--outdir",
        default="./downloads",
        help="Output directory for .md files (default: ./downloads).",
    )
    subparser.add_argument(
        "--verbose",
        action="store_true",
        help="Print full stack traces on error.",
    )


def _collect_urls(cli_urls: list[str], url_file: str | None) -> list[str]:
    urls: list[str] = list(cli_urls or [])
    if url_file:
        for raw in Path(url_file).read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if line and not line.startswith("#"):
                urls.append(line)
    # de-dupe while preserving order
    seen: set[str] = set()
    deduped: list[str] = []
    for u in urls:
        if u not in seen:
            seen.add(u)
            deduped.append(u)
    return deduped


def _run_fetch(url: str, outdir: Path, *, verbose: bool) -> int:
    from dotenv import load_dotenv

    from scrapepipe.router import UnsupportedPlatformError, route
    from scrapepipe.writers.markdown import write_markdown

    load_dotenv()

    try:
        extractor = route(url)
        post = extractor.fetch(url)
        path = write_markdown(post, outdir)
        print(f"Saved: {path}")
        return 0
    except UnsupportedPlatformError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 2
    except Exception as e:
        return _handle_api_error(e, verbose=verbose)


def _run_fetch_many(
    urls: list[str], outdir: Path, *, delay: float, verbose: bool
) -> int:
    from dotenv import load_dotenv

    load_dotenv()

    succeeded = 0
    failed = 0
    for i, url in enumerate(urls, start=1):
        print(f"[{i}/{len(urls)}] {url}")
        code = _run_fetch(url, outdir, verbose=verbose)
        if code == 0:
            succeeded += 1
        else:
            failed += 1
        if i < len(urls) and delay > 0:
            time.sleep(delay)

    print(f"\nDone: {succeeded} succeeded, {failed} failed.")
    return 0 if failed == 0 else 1


def _run_search(
    query: str,
    *,
    limit: int,
    sort: str,
    outdir: Path,
    verbose: bool,
) -> int:
    from dotenv import load_dotenv

    from scrapepipe.extractors.reddit import RedditExtractor
    from scrapepipe.writers.markdown import write_markdown

    load_dotenv()

    try:
        posts = RedditExtractor().search(query, limit=limit, sort=sort)
    except Exception as e:
        return _handle_api_error(e, verbose=verbose)

    if not posts:
        print(f"No results for query: {query!r}")
        return 0

    print(f"Found {len(posts)} post(s) for {query!r}.")
    saved = 0
    for i, post in enumerate(posts, start=1):
        path = write_markdown(post, outdir)
        print(f"[{i}/{len(posts)}] Saved: {path}")
        saved += 1

    print(f"\nDone: {saved} post(s) saved to {outdir}.")
    return 0


def _handle_api_error(exc: Exception, *, verbose: bool) -> int:
    from scrapepipe.extractors.reddit import RedditPostNotFound
    from scrapepipe.extractors.twitter import TwitterPostNotFound

    if isinstance(exc, (RedditPostNotFound, TwitterPostNotFound)):
        print(f"Error: {exc}", file=sys.stderr)
        return 3

    import requests

    if isinstance(exc, requests.exceptions.HTTPError) and exc.response is not None:
        if exc.response.status_code == 429:
            print(
                "Error: rate-limited by the API. Wait and retry later.",
                file=sys.stderr,
            )
            return 4

    if verbose:
        traceback.print_exc()
    else:
        print(f"Error: {exc}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
