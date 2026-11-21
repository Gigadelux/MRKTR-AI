"""Collect a company's public documents into its knowledge-base folder.

Company-agnostic: everything specific to one company comes from the
``kb_sources`` list in ``gitignore/data/<company>/company.yaml``.

Source types
------------
``llms_index``  an ``llms.txt`` index (recursive); every linked ``.md`` page is fetched.
``pages``       a list of site URLs fetched with ``Accept: text/markdown``.
``file``        a single raw file saved as-is (size-capped).

Standard library only, so it runs without installing anything else.
Usage (from the repo root)::

    python -m app.backend.services.kb_scraper --company <Company> [--only name] [--force]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

USER_AGENT = "mrktr-ai-kb-collector"
MAX_FILE_BYTES = 15_000_000
INDEX_LINE = re.compile(r"^\s*[-*]\s*\[(?P<title>.+?)\]\((?P<url>\S+?)\)(?::\s*(?P<desc>.*))?\s*$")
FRONT_MATTER = re.compile(r"\A---\n(?P<body>.*?)\n---\n", re.DOTALL)


@dataclass
class Page:
    """One document to fetch."""

    url: str
    section: str
    title: str = ""
    description: str = ""
    accept_markdown: bool = False
    raw_file: bool = False


@dataclass
class Result:
    url: str
    section: str
    path: str = ""
    status: str = "pending"  # ok | skipped | unavailable | error
    bytes: int = 0
    sha256: str = ""
    collected_at: str = ""
    error: str = ""
    extra: dict = field(default_factory=dict)


# --------------------------------------------------------------------------
# Pure helpers (unit-tested)
# --------------------------------------------------------------------------
def parse_index(text: str) -> list[tuple[str, str, str]]:
    """Return ``(title, url, description)`` for every markdown list link in an index."""
    found = []
    for line in text.splitlines():
        m = INDEX_LINE.match(line)
        if m:
            found.append(
                (m.group("title").strip(), m.group("url").strip(), (m.group("desc") or "").strip())
            )
    return found


def url_to_relpath(url: str, section: str, raw_file: bool = False) -> str:
    """Map a URL to a stable path ``<section>/<slug>.md`` (raw files keep their name)."""
    parsed = urlparse(url)
    path = parsed.path.strip("/")
    if path.startswith("docs/"):
        path = path[len("docs/") :]
    if section and path.startswith(section + "/"):
        path = path[len(section) + 1 :]
    if raw_file:
        name = path.split("/")[-1] or "file"
        return f"{section}/{name}"
    if path.endswith(".md"):
        path = path[:-3]
    path = re.sub(r"[^A-Za-z0-9/_.-]+", "-", path).strip("/") or "home"
    return f"{section}/{path}.md"


def split_front_matter(body: str) -> tuple[dict, str]:
    """Strip a leading YAML front-matter block, returning ``(fields, rest)``; only ``title`` is read."""
    m = FRONT_MATTER.match(body)
    if not m:
        return {}, body
    fields = {}
    t = re.search(r'^title:\s*"?(.*?)"?\s*$', m.group("body"), re.MULTILINE)
    if t:
        fields["title"] = t.group(1)
    return fields, body[m.end() :].lstrip("\n")


def build_front_matter(page: Page, collected_at: str, title: str = "") -> str:
    """Front matter that records where a document came from and when."""
    lines = ["---", f"source_url: {json.dumps(page.url)}", f"section: {json.dumps(page.section)}"]
    title = title or page.title
    if title:
        lines.append(f"title: {json.dumps(title)}")
    if page.description:
        lines.append(f"description: {json.dumps(page.description)}")
    lines += [f"collected_at: {collected_at}", "---", ""]
    return "\n".join(lines)


# --------------------------------------------------------------------------
# Network
# --------------------------------------------------------------------------
def fetch(
    url: str, accept: str | None = None, retries: int = 3, timeout: int = 40
) -> tuple[bytes, str]:
    """GET with retries; returns ``(body, content_type)``. Raises on final failure."""
    headers = {"User-Agent": USER_AGENT}
    if accept:
        headers["Accept"] = accept
    last: Exception | None = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read(MAX_FILE_BYTES + 1), resp.headers.get("Content-Type", "")
        except urllib.error.HTTPError as exc:
            if exc.code in (404, 410):
                raise
            last = exc
        except Exception as exc:  # network hiccup
            last = exc
        time.sleep(1.5 * (attempt + 1))
    assert last is not None
    raise last


def discover(index_url: str, section: str, seen: set, depth: int = 0) -> list[Page]:
    """Walk an ``llms.txt`` index (recursing into nested indexes) and list its pages."""
    if index_url in seen or depth > 3:
        return []
    seen.add(index_url)
    body, _ = fetch(index_url)
    pages: list[Page] = []
    for title, url, desc in parse_index(body.decode("utf-8", "replace")):
        if url.endswith("/llms.txt"):
            pages += discover(url, section, seen, depth + 1)
        elif url.endswith(".md") and url not in seen:
            seen.add(url)
            pages.append(Page(url=url, section=section, title=title, description=desc))
    return pages


def build_page_list(sources: list[dict], only: str | None = None) -> list[Page]:
    pages: list[Page] = []
    seen: set = set()
    for src in sources:
        name = src["name"]
        if only and name != only:
            continue
        kind = src["type"]
        if kind == "llms_index":
            pages += discover(src["index"], name, seen)
        elif kind == "pages":
            for url in src["urls"]:
                pages.append(Page(url=url, section=name, accept_markdown=True))
        elif kind == "file":
            pages.append(Page(url=src["url"], section=name, raw_file=True))
        else:
            raise ValueError(f"unknown kb source type: {kind}")
    return pages


def collect_page(page: Page, kb_dir: Path, collected_at: str, force: bool, delay: float) -> Result:
    rel = url_to_relpath(page.url, page.section, page.raw_file)
    res = Result(url=page.url, section=page.section, path=rel, collected_at=collected_at)
    target = kb_dir / rel
    if target.exists() and not force:
        res.status, res.bytes = "skipped", target.stat().st_size
        res.sha256 = hashlib.sha256(target.read_bytes()).hexdigest()
        return res
    try:
        time.sleep(delay)
        body, ctype = fetch(page.url, accept="text/markdown" if page.accept_markdown else None)
        if len(body) > MAX_FILE_BYTES:
            res.status, res.error = "unavailable", "larger than size cap"
            return res
        if page.accept_markdown and "markdown" not in ctype:
            res.status, res.error = "unavailable", f"no markdown version (got {ctype or 'unknown'})"
            return res
        text = body.decode("utf-8", "replace")
        if page.raw_file:
            out = text
        else:
            fields, rest = split_front_matter(text)
            out = build_front_matter(page, collected_at, fields.get("title", "")) + rest
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(out, encoding="utf-8")
        res.status, res.bytes = "ok", len(out.encode("utf-8"))
        res.sha256 = hashlib.sha256(out.encode("utf-8")).hexdigest()
    except urllib.error.HTTPError as exc:
        res.status, res.error = (
            ("unavailable" if exc.code in (404, 410) else "error"),
            f"HTTP {exc.code}",
        )
    except Exception as exc:
        res.status, res.error = "error", f"{type(exc).__name__}: {exc}"
    return res


def collect(
    sources: list[dict],
    kb_dir: Path,
    collected_at: str,
    only: str | None = None,
    force: bool = False,
    workers: int = 4,
    delay: float = 0.15,
) -> list[Result]:
    """Fetch every page of every source into ``kb_dir`` and write ``_manifest.json``."""
    kb_dir.mkdir(parents=True, exist_ok=True)
    pages = build_page_list(sources, only)
    print(f"{len(pages)} pages to process", file=sys.stderr)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(
            pool.map(lambda p: collect_page(p, kb_dir, collected_at, force, delay), pages)
        )
    write_manifest(kb_dir, collected_at, results, replace_sections={p.section for p in pages})
    return results


def write_manifest(
    kb_dir: Path, collected_at: str, results: list[Result], replace_sections: set
) -> None:
    """Write ``_manifest.json``. Entries of sections not re-collected are kept, so ``--only`` is safe."""
    manifest = kb_dir / "_manifest.json"
    kept: list[dict] = []
    if manifest.is_file():
        previous = json.loads(manifest.read_text(encoding="utf-8")).get("pages", [])
        kept = [p for p in previous if p["section"] not in replace_sections]
    pages = kept + [r.__dict__ for r in results]
    counts = {
        s: sum(p["status"] == s for p in pages) for s in ("ok", "skipped", "unavailable", "error")
    }
    manifest.write_text(
        json.dumps({"collected_at": collected_at, "counts": counts, "pages": pages}, indent=2),
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    import datetime

    import yaml  # only the CLI needs it

    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--company", required=True, help="folder name under gitignore/data/")
    ap.add_argument("--data-root", default="gitignore/data")
    ap.add_argument("--only", help="collect a single named source")
    ap.add_argument("--force", action="store_true", help="re-fetch pages that already exist")
    ap.add_argument(
        "--date", default=datetime.date.today().isoformat(), help="collection date (YYYY-MM-DD)"
    )
    args = ap.parse_args(argv)

    company_dir = Path(args.data_root) / args.company
    profile = yaml.safe_load((company_dir / "company.yaml").read_text(encoding="utf-8"))
    results = collect(profile["kb_sources"], company_dir / "kb", args.date, args.only, args.force)
    counts = {
        s: sum(r.status == s for r in results) for s in ("ok", "skipped", "unavailable", "error")
    }
    print(json.dumps(counts), file=sys.stderr)
    for r in results:
        if r.status in ("unavailable", "error"):
            print(f"  {r.status}: {r.url} ({r.error})", file=sys.stderr)
    return 1 if counts["error"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
