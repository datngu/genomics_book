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
The author dashboard is at `/stats/`.

## Releasing a chapter

First version of a new chapter (choose a short ASCII slug, it becomes the URL `/chapters/<slug>/`):

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

To fix a draft without making a new version, replace the PDF inside the existing release:

```sh
scripts/release.sh rna-seq 0.1.0 build/rna-seq.pdf -r
```

Download counts of the replaced file are kept in the version total.

The preface on the home page is generated from the LaTeX source:

```sh
python scripts/bookctl.py sync-preface
```
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

This text is identical to `LICENSE` and to the copyright page of the website (https://cgbook.dattn.com/license/).
The site build fails if they ever differ.

© 2026 Dat Nguyen. Bảo lưu mọi quyền. Bạn đọc được phép đọc nội dung và chia sẻ bài viết gốc này bằng nút chia sẻ hoặc đường dẫn tới bài gốc. Không được sao chép, đăng lại, phân phối, chỉnh sửa, dịch hoặc sử dụng lại một phần hay toàn bộ nội dung, bao gồm văn bản và hình ảnh, khi chưa có sự đồng ý bằng văn bản của tác giả. Tác giả bảo lưu quyền chỉnh sửa nội dung bất cứ lúc nào mà không cần thông báo trước. Nội dung được cung cấp "nguyên trạng" (as is), chỉ nhằm mục đích học tập và tham khảo, không kèm bất kỳ bảo đảm nào; tác giả không chịu trách nhiệm hay nghĩa vụ đối với bất kỳ việc sử dụng nào từ nội dung này.

© 2026 Dat Nguyen. All rights reserved. You may read this content and share the original post via its link or the share button. No part of this content, including text and figures, may be copied, reposted, redistributed, modified, translated or otherwise reused without the author's prior written permission. The author reserves the right to revise the content at any time without notice. The content is provided "as is", for educational purposes only, without warranty of any kind; the author accepts no responsibility or liability for any use of it.
