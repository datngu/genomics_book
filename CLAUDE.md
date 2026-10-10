# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A static GitHub Pages site for the Vietnamese book "Hệ gen học tính toán và Dữ liệu lớn", released chapter by chapter as PDF drafts.
The book is an evolving stream, not a fixed design: there is no planned table of contents, and chapters have no numbers.
The site UI and content are in Vietnamese.
It is served at `https://cgbook.dattn.com/` (custom domain set in the repo Pages settings, DNS at Porkbun), from the repo `datngu/genomics_book`.
There is no book source here: PDFs are built elsewhere and published as GitHub Releases.

## Commands

```sh
pip install -r requirements.txt                 # jinja2, pyyaml, markdown
python scripts/bookctl.py build --demo          # build _site/ with synthetic data (offline preview)
python scripts/bookctl.py build                 # build _site/ from stats/ (offline)
python -m http.server 8765 -d _site             # serve the build
python scripts/bookctl.py collect               # snapshot releases, downloads, page views (network; GITHUB_TOKEN, GOATCOUNTER_TOKEN)
python scripts/bookctl.py fetch-pdfs            # cache latest chapter PDFs in .pdf-cache/
scripts/release.sh <slug> 0.1.0 file.pdf -t "Title" -n notes.md  # publish a chapter version via gh
```

There are no tests or linters.
To check a change visually, build with `--demo` and screenshot the pages with headless Chrome.

## Architecture

Data flows in one direction: GitHub Releases + GoatCounter → `stats/` (committed) → `_site/` (generated, not committed).

- `book.yml` holds only book metadata (title, repo, site URL, GoatCounter code).
  It has no chapter list.
- Chapters and versions come entirely from GitHub Releases.
  A release counts if its tag matches `<slug>-vX.Y.Z` (`TAG_RE` in `bookctl.py`) and it has a `.pdf` asset.
  The slug is the chapter id and URL (`/chuong/<slug>/`).
  The release title is the chapter title, and the newest version's title wins (`chapter_titles`).
  The release body is the Markdown changelog.
  Chapters are listed by most recent update.
- `collect` writes `stats/releases.json` (reduced release metadata) and upserts today's cumulative per-asset `download_count` into `stats/downloads.csv`.
  It also re-fetches the last 14 days of GoatCounter hits into `stats/views.csv`.
- `fetch-pdfs` downloads the latest PDF per chapter so the site can serve it for online reading under `_site/pdf/`.
  Each real download inflates GitHub's counter, so it is logged in `stats/bot_downloads.csv`, and `compute_stats` subtracts it.
  The workflow keeps `.pdf-cache/` in `actions/cache` so each asset is normally downloaded once.
- `build` is fully offline.
  `compute_stats` turns cumulative snapshots into daily deltas (a day with no snapshot is `null`, and its downloads land on the next snapshot).
  The result is embedded as JSON in `/thong-ke/`, where `static/stats.js` renders tiles, SVG charts and tables client-side.
- Templates use a `root` relative prefix so the site works at any base path.
  The exception is `404.html`, which uses absolute `site_url` links.
- `.github/workflows/site.yml` runs on push to `main`, on release events, daily (cron), and manually.
  It runs collect → fetch-pdfs → build, commits `stats/` back to `main`, and deploys `_site/` with `actions/deploy-pages`.

## Conventions

- URL paths are Vietnamese slugs: `/chuong/<id>/`, `/ban-quyen/`, `/thong-ke/`.
  The stats page is linked in the menu but is `noindex` and disallowed in `robots.txt`.
- The home page must not grow a book introduction or a planned table of contents; the author asked for neither.
- The copyright text in `templates/license.html` is the author's exact wording in Vietnamese and English.
  Do not paraphrase it.
- Chart colors follow the dataviz reference palette (`--series-1` blue for downloads, `--series-2` orange for views).
  Downloads and views always go on separate charts, never on a dual axis.
- `stats/*.csv` are append/upsert histories written by the workflow.
  Do not rewrite them by hand except to fix corrupted data.
