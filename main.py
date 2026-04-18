import argparse
import sys
import traceback
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="scrapepipe",
        description="Fetch a social media post and save it as Markdown.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    fetch_parser = subparsers.add_parser("fetch", help="Fetch one post by URL.")
    fetch_parser.add_argument("url", help="Post URL (Reddit or X/Twitter).")
    fetch_parser.add_argument(
        "--outdir",
        default="./downloads",
        help="Output directory for the .md file (default: ./downloads).",
    )
    fetch_parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print full stack traces on error.",
    )

    args = parser.parse_args(argv)

    if args.command == "fetch":
        return _run_fetch(args.url, Path(args.outdir), verbose=args.verbose)

    parser.print_help()
    return 1


def _run_fetch(url: str, outdir: Path, *, verbose: bool) -> int:
    # Imports deferred so `--help` doesn't require the deps to be installed.
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


def _handle_api_error(exc: Exception, *, verbose: bool) -> int:
    # Lazy import so deps aren't required for --help.
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
