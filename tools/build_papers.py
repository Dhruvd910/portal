"""build_papers.py -- turn tools/papers.tsv into the portal's question-paper library.

Writes ../papers.json (what papers.html lists), downloads every file into OUT/<exam>/<year>/, and zips one bundle per
exam into OUT/bundles/. Only official papers and keys: live on the exam body's site, or the Wayback Machine's exact
copy of a file the exam body published (its "id_" link returns the original bytes).

    python tools/build_papers.py [OUT]      (OUT defaults to ~/Desktop/Question-Papers)
"""
import json, re, sys, time, urllib.request, zipfile
from pathlib import Path

HERE = Path(__file__).parent
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.home() / "Desktop" / "Question-Papers"
UA = {"User-Agent": "Mozilla/5.0 (question-paper library)"}


def link(src, url):
    return url if src == "live" else f"https://web.archive.org/web/{src}id_/{url}"


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def fetch(url, dest):  # archive over http: its https chain fails strict OpenSSL 3 checks here
    if dest.exists() and dest.stat().st_size > 1000:
        return True
    for i in range(4):
        try:
            data = urllib.request.urlopen(urllib.request.Request(url.replace("https://web.archive.org", "http://web.archive.org"), headers=UA), timeout=300).read()
            break
        except Exception as e:
            err = e; time.sleep(6 * (i + 1))
    else:
        print("FAIL", dest.name, err); return False
    if b"%PDF" not in data[:1024]:
        print("NOT A PDF", dest.name); return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    print("ok", dest.relative_to(OUT), len(data) // 1024, "KB", flush=True)
    return True


rows = []
for line in (HERE / "papers.tsv").read_text(encoding="utf-8").splitlines():
    if line.strip() and not line.startswith("#"):
        exam, year, title, kind, src, url = line.split("\t")
        rows.append(dict(exam=exam, year=int(year), title=title, kind=kind, url=link(src, url),
                         archived=src != "live", file=f"{slug(exam)}/{year}/{slug(exam)}-{year}-{slug(title)}.pdf"))
rows.sort(key=lambda r: (r["exam"], -r["year"], r["kind"] == "key", r["title"]))
assert len({r["file"] for r in rows}) == len(rows), "two manifest rows map to one file name"

ok = [r for r in rows if fetch(r["url"], OUT / r["file"])]
(HERE.parent / "papers.json").write_text(json.dumps(
    [{k: r[k] for k in ("exam", "year", "title", "kind", "url", "archived")} for r in ok], indent=1, ensure_ascii=False),
    encoding="utf-8")

(OUT / "bundles").mkdir(parents=True, exist_ok=True)
for exam in sorted({r["exam"] for r in ok}):
    mine = [r for r in ok if r["exam"] == exam]
    years = f"{min(r['year'] for r in mine)}-{max(r['year'] for r in mine)}"
    with zipfile.ZipFile(OUT / "bundles" / f"{slug(exam)}-{years}.zip", "w", zipfile.ZIP_STORED) as z:  # PDFs are already compressed
        for r in mine:
            z.write(OUT / r["file"], r["file"])
    print("bundle", exam, years, len(mine), "files")
print(f"{len(ok)}/{len(rows)} files; papers.json written")
