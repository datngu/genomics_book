#!/usr/bin/env python3
"""Collect statistics and build the static book site.

Subcommands:
  collect      Snapshot GitHub release metadata, cumulative PDF download counts
               and GoatCounter page views into stats/ (needs network and tokens).
  fetch-pdfs   Download the latest PDF of each chapter into .pdf-cache/ so the site
               can offer online reading. Every real download is logged in
               stats/bot_downloads.csv and subtracted from the reader counts.
  build        Render the site into _site/ from book.yml and stats/ (offline).
               With --demo, use synthetic releases and statistics instead.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import random
import re
import shutil
import sys
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATS = ROOT / "stats"
OUT = ROOT / "_site"
CACHE = ROOT / ".pdf-cache"
TEMPLATES = ROOT / "templates"
STATIC = ROOT / "static"

RELEASES_JSON = STATS / "releases.json"
DOWNLOADS_CSV = STATS / "downloads.csv"
BOT_CSV = STATS / "bot_downloads.csv"
VIEWS_CSV = STATS / "views.csv"

DOWNLOAD_FIELDS = ["date", "tag", "asset_id", "asset_name", "download_count"]
BOT_FIELDS = ["date", "asset_id"]
VIEW_FIELDS = ["date", "path", "title", "event", "views"]

# A chapter release is tagged "<slug>-v<semver>", e.g. "rna-seq-v0.2.0". The release title is the chapter title.
TAG_RE = re.compile(r"^(?P<chapter>[a-z0-9]+(?:-[a-z0-9]+)*)-v(?P<version>\d+\.\d+\.\d+)$")
VIEWS_WINDOW_DAYS = 14  # GoatCounter days re-fetched on every collect, to absorb late hits.


def today() -> date:
    return datetime.now(timezone.utc).date()


def load_book() -> dict:
    import yaml

    with open(ROOT / "book.yml", encoding="utf-8") as f:
        return yaml.safe_load(f)


# ---------------------------------------------------------------- CSV helpers


def read_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, fields: list[str], rows: list[dict]) -> None:
    rows = sorted(rows, key=lambda r: tuple(str(r[k]) for k in fields))
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


# ---------------------------------------------------------------- HTTP


def http_json(url: str, headers: dict | None = None) -> tuple[object, dict]:
    req = urllib.request.Request(url, headers={"User-Agent": "genomics-book-site", **(headers or {})})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.load(resp), dict(resp.headers)


def github_headers() -> dict:
    h = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def fetch_releases(repo: str) -> list[dict]:
    """All published chapter releases of `repo`, reduced to the fields the site uses."""
    url = f"https://api.github.com/repos/{repo}/releases?per_page=100"
    raw: list[dict] = []
    while url:
        page, headers = http_json(url, github_headers())
        raw.extend(page)
        m = re.search(r'<([^>]+)>;\s*rel="next"', headers.get("Link", ""))
        url = m.group(1) if m else None

    releases = []
    for r in raw:
        m = TAG_RE.match(r["tag_name"])
        if r.get("draft") or not m:
            continue
        releases.append(
            {
                "tag": r["tag_name"],
                "chapter": m["chapter"],
                "version": m["version"],
                "name": r.get("name") or r["tag_name"],
                "published_at": r["published_at"],
                "notes": r.get("body") or "",
                "html_url": r["html_url"],
                "assets": [
                    {
                        "id": a["id"],
                        "name": a["name"],
                        "size": a["size"],
                        "download_count": a["download_count"],
                        "url": a["browser_download_url"],
                    }
                    for a in r.get("assets", [])
                    if a["name"].lower().endswith(".pdf")
                ],
            }
        )
    releases.sort(key=lambda r: r["tag"])
    return releases


def fetch_goatcounter(code: str, token: str, start: date, end: date) -> list[dict]:
    """Daily hits per path from the GoatCounter API, as VIEW_FIELDS rows."""
    base = f"https://{code}.goatcounter.com/api/v0/stats/hits"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    rows: list[dict] = []
    seen: list[str] = []
    while True:
        params = [("start", start.isoformat()), ("end", end.isoformat()), ("daily", "true"), ("limit", "100")]
        params += [("exclude_paths", pid) for pid in seen]
        data, _ = http_json(f"{base}?{urllib.parse.urlencode(params)}", headers)
        hits = data.get("hits") or []
        new = [h for h in hits if str(h.get("path_id")) not in seen]
        for h in new:
            seen.append(str(h.get("path_id")))
            for s in h.get("stats") or []:
                n = int(s.get("daily") or 0)
                if n:
                    rows.append(
                        {
                            "date": s["day"][:10],
                            "path": h.get("path", ""),
                            "title": h.get("title", ""),
                            "event": "1" if h.get("event") else "0",
                            "views": n,
                        }
                    )
        if not data.get("more") or not new:
            return rows


# ---------------------------------------------------------------- collect


def cmd_collect(_args) -> None:
    book = load_book()
    repo = os.environ.get("GITHUB_REPOSITORY") or book["repo"]
    day = today().isoformat()
    STATS.mkdir(exist_ok=True)

    releases = fetch_releases(repo)
    RELEASES_JSON.write_text(json.dumps(releases, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    rows = [r for r in read_csv(DOWNLOADS_CSV) if r["date"] != day]
    for rel in releases:
        for a in rel["assets"]:
            rows.append(
                {"date": day, "tag": rel["tag"], "asset_id": a["id"], "asset_name": a["name"], "download_count": a["download_count"]}
            )
    write_csv(DOWNLOADS_CSV, DOWNLOAD_FIELDS, rows)
    print(f"collect: {len(releases)} releases from {repo}, download snapshot for {day}")

    code = os.environ.get("GOATCOUNTER_CODE") or book.get("goatcounter")
    token = os.environ.get("GOATCOUNTER_TOKEN")
    if not (code and token):
        print("collect: GoatCounter code or token missing, page views skipped")
        return
    start = today() - timedelta(days=VIEWS_WINDOW_DAYS)
    fetched = fetch_goatcounter(code, token, start, today())
    kept = [r for r in read_csv(VIEWS_CSV) if r["date"] < start.isoformat()]
    write_csv(VIEWS_CSV, VIEW_FIELDS, kept + fetched)
    print(f"collect: {len(fetched)} page-view rows since {start}")


# ---------------------------------------------------------------- fetch-pdfs


def latest_per_chapter(releases: list[dict]) -> dict[str, dict]:
    latest: dict[str, dict] = {}
    for r in releases:
        cur = latest.get(r["chapter"])
        if cur is None or semver(r["version"]) > semver(cur["version"]):
            latest[r["chapter"]] = r
    return latest


def cmd_fetch_pdfs(_args) -> None:
    releases = json.loads(RELEASES_JSON.read_text(encoding="utf-8")) if RELEASES_JSON.exists() else []
    CACHE.mkdir(exist_ok=True)
    bots = read_csv(BOT_CSV)
    for rel in latest_per_chapter(releases).values():
        for a in rel["assets"][:1]:
            target = CACHE / f"{a['id']}.pdf"
            if target.exists():
                continue
            req = urllib.request.Request(a["url"], headers={"User-Agent": "genomics-book-site"})
            with urllib.request.urlopen(req, timeout=300) as resp, open(target, "wb") as f:
                shutil.copyfileobj(resp, f)
            bots.append({"date": today().isoformat(), "asset_id": a["id"]})
            print(f"fetch-pdfs: cached {a['name']}")
    write_csv(BOT_CSV, BOT_FIELDS, bots)


# ---------------------------------------------------------------- statistics


def semver(v: str) -> tuple[int, ...]:
    return tuple(int(x) for x in v.split("."))


def chapter_titles(releases: list[dict]) -> dict[str, str]:
    """Chapter title = title of its newest release, so renaming a chapter takes one release."""
    return {
        ch: (r["name"] if r["name"] != r["tag"] else ch)
        for ch, r in latest_per_chapter(releases).items()
    }


def compute_stats(releases: list[dict], downloads: list[dict], bots: list[dict], views: list[dict], end: date) -> dict:
    """Turn raw snapshots into the dashboard data set (see static/stats.js)."""
    # Bot downloads per asset, cumulative by date, so they can be subtracted from GitHub's counter.
    bot_events: dict[str, list[str]] = {}
    for b in bots:
        bot_events.setdefault(str(b["asset_id"]), []).append(b["date"])

    def net(asset_id: str, day: str, raw: int) -> int:
        return max(0, raw - sum(1 for d in bot_events.get(asset_id, []) if d <= day))

    series: dict[str, list[tuple[str, int]]] = {}
    tag_of: dict[str, str] = {}
    for r in downloads:
        aid = str(r["asset_id"])
        tag_of[aid] = r["tag"]
        series.setdefault(aid, []).append((r["date"], int(r["download_count"])))

    snapshot_days: set[str] = set()
    daily_dl: dict[str, int] = {}
    total_by_tag: dict[str, int] = {}
    for aid, points in series.items():
        prev = 0
        for day, raw in sorted(points):
            value = net(aid, day, raw)
            snapshot_days.add(day)
            daily_dl[day] = daily_dl.get(day, 0) + max(0, value - prev)
            prev = value
        total_by_tag[tag_of[aid]] = total_by_tag.get(tag_of[aid], 0) + prev

    daily_views: dict[str, int] = {}
    page_totals: dict[tuple[str, bool], dict] = {}
    recent_cut = (end - timedelta(days=29)).isoformat()
    for v in views:
        n = int(v["views"])
        is_event = v.get("event") == "1"
        if not is_event:
            daily_views[v["date"]] = daily_views.get(v["date"], 0) + n
        p = page_totals.setdefault((v["path"], is_event), {"path": v["path"], "title": v.get("title", ""), "event": is_event, "total": 0, "last30": 0})
        p["total"] += n
        if v["date"] >= recent_cut:
            p["last30"] += n

    first_candidates = [min(snapshot_days)] if snapshot_days else []
    if daily_views:
        first_candidates.append(min(daily_views))
    days = []
    if first_candidates:
        d = date.fromisoformat(min(first_candidates))
        while d <= end:
            key = d.isoformat()
            days.append(
                {
                    "date": key,
                    "downloads": daily_dl.get(key) if key in snapshot_days else None,
                    "views": daily_views.get(key, 0) if views else None,
                }
            )
            d += timedelta(days=1)

    titles = chapter_titles(releases)
    latest = latest_per_chapter(releases)
    chapter_totals = {cid: 0 for cid in sorted(latest, key=lambda c: latest[c]["published_at"], reverse=True)}
    versions = []
    for r in releases:
        n = total_by_tag.get(r["tag"], 0)
        chapter_totals[r["chapter"]] = chapter_totals.get(r["chapter"], 0) + n
        versions.append({"chapter": r["chapter"], "title": titles.get(r["chapter"], r["chapter"]), "version": r["version"], "tag": r["tag"], "published": r["published_at"][:10], "downloads": n})
    versions.sort(key=lambda v: (v["published"], v["tag"]), reverse=True)

    return {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "has_views": bool(views),
        "days": days,
        "chapters": [{"id": cid, "title": titles.get(cid, cid), "downloads": n} for cid, n in chapter_totals.items()],
        "versions": versions,
        "pages": sorted(page_totals.values(), key=lambda p: -p["total"])[:50],
    }


# ---------------------------------------------------------------- demo data


def demo_data(book: dict, end: date) -> tuple[list[dict], list[dict], list[dict], list[dict]]:
    """Synthetic releases, snapshots and views so the site can be previewed offline."""
    rng = random.Random(7)
    titles = {
        "nhap-mon": "Hệ gen học tính toán là gì?",
        "giai-trinh-tu": "Dữ liệu giải trình tự thế hệ mới",
        "du-lieu-lon": "Xử lý dữ liệu hệ gen quy mô lớn",
    }
    plan = [("nhap-mon", "0.1.0", 120), ("giai-trinh-tu", "0.1.0", 80), ("nhap-mon", "0.2.0", 45), ("du-lieu-lon", "0.1.0", 20)]
    notes = {
        "0.1.0": "Bản nháp đầu tiên.\n\n- Toàn bộ nội dung chương\n- Hình minh hoạ sơ bộ",
        "0.2.0": "- Sửa lỗi chính tả và thuật ngữ\n- Bổ sung phần bài tập cuối chương\n- Vẽ lại hình 1.3",
    }
    releases, downloads, views = [], [], []
    start = end - timedelta(days=max(age for *_, age in plan))
    for aid, (ch, ver, age) in enumerate(plan, start=1000):
        tag = f"{ch}-v{ver}"
        published = end - timedelta(days=age)
        releases.append(
            {
                "tag": tag, "chapter": ch, "version": ver, "name": titles[ch],
                "published_at": f"{published.isoformat()}T09:00:00Z", "notes": notes[ver],
                "html_url": f"https://github.com/{book['repo']}/releases/tag/{tag}",
                "assets": [{"id": aid, "name": f"{tag}.pdf", "size": 2_400_000, "download_count": 0, "url": f"https://github.com/{book['repo']}/releases/download/{tag}/{tag}.pdf"}],
            }
        )
        count, d = 0, published
        while d <= end:
            if d > published + timedelta(days=3) and rng.random() < 0.08:
                d += timedelta(days=1)  # simulate a missed daily snapshot
                continue
            age_days = (d - published).days
            count += int(rng.expovariate(1 / (2 + 25 * 0.93 ** age_days)))
            downloads.append({"date": d.isoformat(), "tag": tag, "asset_id": aid, "asset_name": f"{tag}.pdf", "download_count": count})
            d += timedelta(days=1)

    paths = [("/", "Trang chủ", 30)] + [(f"/chuong/{c}/", t, 10) for c, t in titles.items()] + [("/ban-quyen/", "Bản quyền", 1)]
    d = start
    while d <= end:
        weekday_boost = 1.3 if d.weekday() < 5 else 0.7
        growth = 0.4 + 0.6 * (d - start).days / max(1, (end - start).days)
        for path, title, base in paths:
            n = int(rng.expovariate(1 / (base * weekday_boost * growth)))
            if n:
                views.append({"date": d.isoformat(), "path": path, "title": title, "event": "0", "views": n})
        d += timedelta(days=1)
    return releases, downloads, [], views


def demo_pdf(text: str) -> bytes:
    """A one-page PDF placeholder (ASCII text only)."""
    stream = f"BT /F1 24 Tf 72 720 Td ({text}) Tj ET".encode()
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, body in enumerate(objs, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    out += b"".join(f"{o:010d} 00000 n \n".encode() for o in offsets)
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return bytes(out)


# ---------------------------------------------------------------- build


@dataclass
class Chapter:
    id: str
    title: str
    versions: list[dict] = field(default_factory=list)  # newest first
    online_pdf: str | None = None  # path under _site, when a copy is available
    downloads: int = 0

    @property
    def latest(self) -> dict | None:
        return self.versions[0] if self.versions else None


def human_size(n: int) -> str:
    return f"{n / 1_000_000:.1f} MB".replace(".", ",")


def vi_date(iso: str) -> str:
    d = date.fromisoformat(iso[:10])
    return f"{d.day:02d}/{d.month:02d}/{d.year}"


def cmd_build(args) -> None:
    import jinja2
    import markdown

    book = load_book()
    end = today()
    if args.demo:
        releases, downloads, bots, views = demo_data(book, end)
    else:
        releases = json.loads(RELEASES_JSON.read_text(encoding="utf-8")) if RELEASES_JSON.exists() else []
        downloads, bots, views = read_csv(DOWNLOADS_CSV), read_csv(BOT_CSV), read_csv(VIEWS_CSV)

    stats = compute_stats(releases, downloads, bots, views, end)
    stats["demo"] = args.demo
    downloads_by_tag = {v["tag"]: v["downloads"] for v in stats["versions"]}

    if OUT.exists():
        shutil.rmtree(OUT)
    shutil.copytree(STATIC, OUT / "static")
    (OUT / ".nojekyll").touch()
    host = urllib.parse.urlparse(book["site_url"]).hostname
    if host and not host.endswith(".github.io"):
        (OUT / "CNAME").write_text(host + "\n", encoding="utf-8")

    # Chapters exist only once released, ordered by their most recent update.
    latest = latest_per_chapter(releases)
    titles = chapter_titles(releases)
    chapters: list[Chapter] = []
    for cid in sorted(latest, key=lambda c: latest[c]["published_at"], reverse=True):
        ch = Chapter(id=cid, title=titles[cid])
        for r in sorted((r for r in releases if r["chapter"] == cid), key=lambda r: semver(r["version"]), reverse=True):
            asset = r["assets"][0] if r["assets"] else None
            ch.versions.append(
                {
                    **r,
                    "date": vi_date(r["published_at"]),
                    "notes_html": markdown.markdown(r["notes"]),
                    "pdf_url": asset["url"] if asset else r["html_url"],
                    "pdf_size": human_size(asset["size"]) if asset else "",
                    "downloads": downloads_by_tag.get(r["tag"], 0),
                }
            )
        if ch.latest and ch.latest["assets"]:
            asset = ch.latest["assets"][0]
            dest = OUT / "pdf" / asset["name"]
            dest.parent.mkdir(exist_ok=True)
            cached = CACHE / f"{asset['id']}.pdf"
            if args.demo:
                dest.write_bytes(demo_pdf(f"Demo: {ch.latest['tag']}"))
            elif cached.exists():
                shutil.copyfile(cached, dest)
            if dest.exists():
                ch.online_pdf = f"pdf/{asset['name']}"
        ch.downloads = sum(v["downloads"] for v in ch.versions)
        chapters.append(ch)

    updates = sorted(
        ({"chapter": ch, "version": v} for ch in chapters for v in ch.versions),
        key=lambda u: u["version"]["published_at"],
        reverse=True,
    )

    env = jinja2.Environment(loader=jinja2.FileSystemLoader(TEMPLATES), autoescape=True, trim_blocks=True, lstrip_blocks=True)
    site_url = book["site_url"].rstrip("/") + "/"
    common = {"book": book, "chapters": chapters, "demo": args.demo, "year": book.get("year", end.year), "build_date": vi_date(end.isoformat())}

    def render(template: str, path: str, **ctx) -> None:
        # "dir/" renders dir/index.html; "name.ext" renders a top-level file.
        target = OUT / path if "." in path else OUT / path / "index.html"
        depth = path.count("/")
        target.parent.mkdir(parents=True, exist_ok=True)
        root = ctx.pop("root", "../" * depth)
        html = env.get_template(template).render(**common, **ctx, root=root, page_path=path, canonical=site_url + path)
        target.write_text(html, encoding="utf-8")

    render("index.html", "", updates=updates[:8])
    for ch in chapters:
        render("chapter.html", f"chuong/{ch.id}/", chapter=ch)
    render("license.html", "ban-quyen/")
    render("stats.html", "thong-ke/", stats_json=json.dumps(stats, ensure_ascii=False).replace("</", "<\\/"))
    render("404.html", "404.html", root=site_url)  # served at any depth, so links must be absolute
    render("feed.xml", "feed.xml", updates=updates, site_url=site_url, now=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))

    (OUT / "robots.txt").write_text(f"User-agent: *\nDisallow: /thong-ke/\nSitemap: {site_url}sitemap.xml\n", encoding="utf-8")
    pages = ["", "ban-quyen/"] + [f"chuong/{ch.id}/" for ch in chapters]
    sitemap = "".join(f"  <url><loc>{site_url}{p}</loc></url>\n" for p in pages)
    (OUT / "sitemap.xml").write_text(
        f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{sitemap}</urlset>\n',
        encoding="utf-8",
    )
    print(f"build: {len(chapters)} chapters, {len(releases)} releases -> {OUT.relative_to(ROOT)}/" + (" (demo data)" if args.demo else ""))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("collect").set_defaults(func=cmd_collect)
    sub.add_parser("fetch-pdfs").set_defaults(func=cmd_fetch_pdfs)
    b = sub.add_parser("build")
    b.add_argument("--demo", action="store_true", help="use synthetic releases and statistics")
    b.set_defaults(func=cmd_build)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    sys.exit(main())
