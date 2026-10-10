# Hệ gen học tính toán và Dữ liệu lớn

Website for the Vietnamese book on computational genomics and big data by Dat Nguyen.
The book grows as a continuous stream of chapter drafts in PDF, not as a fixed table of contents.
Each chapter has its own version history.
The site is static, built by `scripts/bookctl.py`, and deployed to GitHub Pages by `.github/workflows/site.yml`.

## Preview locally

```sh
pip install -r requirements.txt
python scripts/bookctl.py build --demo   # synthetic releases and statistics
python -m http.server 8765 -d _site      # open http://localhost:8765/
```

Drop `--demo` to build from the real data in `stats/`.
The author dashboard is at `/thong-ke/`.

## Releasing a chapter

First version of a new chapter (choose a short ASCII slug, it becomes the URL `/chuong/<slug>/`):

```sh
scripts/release.sh rna-seq 0.1.0 build/rna-seq.pdf -t "Phân tích dữ liệu RNA-seq" -n notes.md
```

Later versions reuse the previous title unless `-t` is given (pass `-t` to rename the chapter):

```sh
scripts/release.sh rna-seq 0.2.0 build/rna-seq.pdf -n notes.md
```

This creates the GitHub Release `rna-seq-v0.2.0` with the asset `rna-seq-v0.2.0.pdf`.
The release notes (Markdown, optional) become the changelog on the site.
Publishing the release triggers a rebuild.
A chapter appears on the site with its first release, and chapters are ordered by most recent update.
The newest version of each chapter becomes the one shown and read online.

The display order and chapter numbers are set in `book.yml` under `chapters` (`slug` and an optional `label` such as "Chương 1").
Changing them is a normal commit and does not create a new version.
A released chapter missing from that list is shown last.
Older versions stay downloadable from the chapter page.
Use `0.x.y` versions while the chapter is a draft.

## Statistics

- **Downloads** come from GitHub's per-asset `download_count`.
  The daily job stores cumulative snapshots in `stats/downloads.csv`, and the dashboard turns them into daily numbers.
  The build itself downloads each new PDF once for online reading.
  Those downloads are logged in `stats/bot_downloads.csv` and subtracted.
- **Page views** come from [GoatCounter](https://www.goatcounter.com) (free, no cookies).
  Clicks on read, download and share buttons are recorded as GoatCounter events.

The workflow runs daily at 03:17 UTC, commits the new snapshot to `main`, and redeploys.

The dashboard is linked as *Thống kê* in the menu and is marked `noindex` for search engines.
It is public, because GitHub Pages has no access control.

## One-time setup

1. The code lives in `datngu/genomics_book`, and the site is served at `https://cgbook.dattn.com/`.
   Change `repo` and `site_url` in `book.yml` if either moves.
2. In *Settings → Pages*, *Source* is **GitHub Actions** and the custom domain is `cgbook.dattn.com`.
   DNS (Porkbun): `CNAME` record `cgbook` → `datngu.github.io`.
   In *Settings → Environments → github-pages*, deployments are allowed from `main` and from tags matching `*-v*.*.*`, so release events can deploy.
3. For page views, create a GoatCounter site, then:
   - set `goatcounter: "<code>"` in `book.yml`,
   - add the repository variable `GOATCOUNTER_CODE` with the same code,
   - create an API token with read-statistics permission, and add it as the repository secret `GOATCOUNTER_TOKEN`.
4. Run the *Site* workflow once manually (*Actions → Site → Run workflow*).

## License

© 2026 Dat Nguyen. All rights reserved.
See `/ban-quyen/` on the site for the full terms in Vietnamese and English.
