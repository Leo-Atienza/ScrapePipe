# ScrapePipe

Fetch a social media post by URL and save it as a formatted Markdown file — ready to feed to an LLM.

**Supported platforms (v1):** Reddit, X/Twitter.

## What you get

Each run writes one `.md` file per post containing:

- **Header:** author, handle, platform, post date, URL, like/comment counts
- **Body:** full post text (Reddit selftext or tweet text)
- **Images:** embedded image URLs as Markdown `![]()` links
- **Comments (Reddit only):** the full nested reply tree rendered with `>` blockquote depth — perfect for LLM context
- **Filename:** `{platform}_{YYYY-MM-DD}_{author}_{post_id}.md`

X/Twitter posts use the public oEmbed endpoint, which does not expose like/reply counts or comments — those fields will be `0`. Text, author, handle, images, and date are extracted cleanly.

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

**None required.** ScrapePipe v1 uses public endpoints for both platforms:
- **Reddit:** public JSON endpoint (`.json` appended to any post URL).
- **X/Twitter:** public oEmbed endpoint (`publish.twitter.com/oembed`).

### 4. (Optional) Create a `.env`

Only needed if you want to override the default User-Agent string Reddit sees:

```powershell
copy .env.example .env
notepad .env
```

Set `REDDIT_USER_AGENT` to something descriptive (e.g. `ScrapePipe/0.1 by u/<your_reddit_username>`). Skip this step entirely if you don't care.

## Usage

Activate your venv first (every new terminal):

```powershell
.\venv\Scripts\Activate.ps1
```

### 1. Fetch one post

Copy any Reddit or X/Twitter URL from your browser and pass it to `fetch`:

```powershell
python main.py fetch "https://www.reddit.com/r/python/comments/abc123/some_slug/"
python main.py fetch "https://x.com/jack/status/20"
```

The tool prints the path to the generated `.md` file. Default output directory is `./downloads`.

### 2. Fetch many posts at once

Pass URLs as arguments:
```powershell
python main.py fetch-many "<url1>" "<url2>" "<url3>"
```

Or put one URL per line in a text file (blank lines and `#` comments are ignored):
```powershell
python main.py fetch-many --file urls.txt
```

`fetch-many` continues on per-URL errors and prints a summary at the end. Default 1-second delay between requests — tune with `--delay`.

### 3. Search Reddit by topic

```powershell
python main.py search "python dataclass" --limit 10 --sort top
```

Writes one `.md` file per matching post. Valid `--sort` values: `relevance` (default), `top`, `new`, `hot`, `comments`.

> `search` is Reddit-only — X/Twitter search requires paid API access. For X, collect tweet URLs manually and feed them to `fetch-many`.

### Common flags

| Flag | Applies to | Default | Purpose |
|---|---|---|---|
| `--outdir PATH` | all | `./downloads` | Where to write `.md` files |
| `--delay SECONDS` | `fetch-many` | `1.0` | Wait between requests |
| `--verbose` | all | off | Print full stack trace on error |

### Typical workflow

1. Copy a post URL from Reddit or X.
2. Run `python main.py fetch "<url>"`.
3. Open the `.md` file in `./downloads/` (or paste its path into Claude).

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
