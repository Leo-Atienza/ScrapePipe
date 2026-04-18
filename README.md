# ScrapePipe

Fetch a social media post by URL and save it as a formatted Markdown file.

**Supported platforms (v1):** Reddit, X/Twitter.

## Setup

### 1. Install Python 3.10+

```powershell
python --version
```

### 2. Clone and create a virtual environment

```powershell
cd ScrapePipe
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 3. Credentials

No credentials required. ScrapePipe v1 uses public endpoints for both platforms:
- **Reddit:** public JSON endpoint (append `.json` to any post URL).
- **X/Twitter:** public oEmbed endpoint at `publish.twitter.com/oembed`.

Optionally set a descriptive `REDDIT_USER_AGENT` in `.env`.

**Data loss note for X:** oEmbed does not expose like/reply counts, so those fields will be `0` in output. Text, author, handle, images, and post date are extracted cleanly.

### 4. Create your `.env`

```powershell
copy .env.example .env
```

Edit `.env` and fill in your credentials.

## Usage

```powershell
python main.py fetch "https://www.reddit.com/r/python/comments/<id>/<slug>/"
python main.py fetch "https://x.com/<user>/status/<tweet_id>"
```

Options:
- `--outdir PATH` — where to save the `.md` file (default: `./downloads`).
- `--verbose` — print full stack trace on error.

## Exit codes

| Code | Meaning |
|---|---|
| 0 | Success |
| 1 | Generic error |
| 2 | Unsupported URL |
| 3 | Post not found or deleted |
| 4 | Rate-limited by API |

## Project layout

```
scrapepipe/
├── models.py         # SocialPost dataclass
├── router.py         # URL -> platform dispatcher
├── extractors/       # Platform-specific fetchers (Reddit, Twitter)
├── writers/          # Output formatters (Markdown)
└── utils/            # Filename sanitizer etc.
main.py               # CLI entry point
```

## Roadmap

- v2: Meta (Instagram/Facebook) via Apify
- v2: Streamlit GUI
- v2: `.txt` and JSON output
- v2: Batch mode, rate-limit auto-retry, image downloads
