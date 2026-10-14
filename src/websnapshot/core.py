"""Local crawler, snapshots, comparison and HTML reporting."""
from __future__ import annotations
from collections import deque
from datetime import datetime, timezone
from difflib import unified_diff
from hashlib import sha256
from html import escape
import ipaddress
import json
import os
from pathlib import Path
import re
import socket
import sqlite3
from urllib.parse import urldefrag, urljoin, urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser

from bs4 import BeautifulSoup
import requests

DATA = Path(os.environ.get("WEBSNAPSHOT_DATA_DIR", ".data")).resolve()
AGENT = "WebSnapshot/0.1 (local manual archive)"
MAX_BYTES = 2_000_000


def normalize_url(value: str) -> str:
    url, _ = urldefrag(value.strip())
    p = urlsplit(url)
    if p.scheme not in ("https", "http") or not p.hostname or p.username or p.password:
        raise ValueError("Please enter a public http(s) URL without credentials")
    port = f":{p.port}" if p.port else ""
    return urlunsplit((p.scheme, p.hostname.lower() + port, p.path or "/", p.query, ""))


def check_public(url: str) -> None:
    host = urlsplit(url).hostname
    if not host or host.lower() == "localhost" or host.endswith(".local"):
        raise ValueError("Private hosts are blocked")
    try:
        addresses = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise ValueError(f"DNS resolution failed: {host}") from exc
    if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
        raise ValueError("Private or reserved IP addresses are blocked")


def extract(html: str, base: str) -> tuple[str, str, list[str]]:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg", "template"]):
        tag.decompose()
    title = soup.title.get_text(" ", strip=True) if soup.title else base
    main = soup.find("main") or soup.find("article") or soup.body or soup
    content = "\n".join(re.sub(r"\s+", " ", s).strip() for s in main.stripped_strings)
    links = []
    for a in soup.find_all("a", href=True):
        try:
            links.append(normalize_url(urljoin(base, a["href"])))
        except (ValueError, TypeError):
            pass
    return title, content, list(dict.fromkeys(links))


def database(data: Path = DATA) -> Path:
    data.mkdir(parents=True, exist_ok=True)
    path = data / "websnapshot.sqlite3"
    with sqlite3.connect(path) as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS sites(id INTEGER PRIMARY KEY, url TEXT UNIQUE NOT NULL, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS runs(id INTEGER PRIMARY KEY, site_id INTEGER NOT NULL,
            created_at TEXT NOT NULL, status TEXT NOT NULL, errors TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS pages(run_id INTEGER NOT NULL, url TEXT NOT NULL,
            title TEXT NOT NULL, content TEXT NOT NULL, digest TEXT NOT NULL,
            PRIMARY KEY(run_id,url));
        """)
    return path


def add_site(url: str, data: Path = DATA) -> None:
    url = normalize_url(url)
    check_public(url)
    with sqlite3.connect(database(data)) as db:
        db.execute("INSERT OR IGNORE INTO sites(url,created_at) VALUES (?,?)",
                   (url, datetime.now(timezone.utc).isoformat()))


def sites(data: Path = DATA) -> list[tuple[int, str]]:
    with sqlite3.connect(database(data)) as db:
        return db.execute("SELECT id,url FROM sites ORDER BY id DESC").fetchall()


def runs(site_id: int, data: Path = DATA) -> list[tuple]:
    with sqlite3.connect(database(data)) as db:
        return db.execute("SELECT id,created_at,status,errors FROM runs WHERE site_id=? ORDER BY id DESC",
                          (site_id,)).fetchall()


def crawl(start: str, limit: int = 30, depth_limit: int = 2) -> tuple[dict, list[str]]:
    start = normalize_url(start)
    check_public(start)
    origin = urlsplit(start).netloc
    robot = RobotFileParser()
    robot.set_url(f"{urlsplit(start).scheme}://{origin}/robots.txt")
    robot_ok = True
    try:
        robot.read()
    except Exception:
        robot_ok = False
    client = requests.Session()
    client.headers.update({"User-Agent": AGENT})
    queue = deque([(start, 0)])
    seen = set()
    pages = {}
    errors = []
    while queue and len(pages) < limit:
        url, depth = queue.popleft()
        if url in seen:
            continue
        seen.add(url)
        try:
            check_public(url)
            if robot_ok and not robot.can_fetch(AGENT, url):
                errors.append(f"robots.txt disallows: {url}")
                continue
            with client.get(url, timeout=(5, 20), stream=True, allow_redirects=False) as response:
                if response.is_redirect:
                    errors.append(f"Redirect not followed: {url}")
                    continue
                response.raise_for_status()
                if "text/html" not in response.headers.get("Content-Type", "").lower():
                    errors.append(f"Not HTML: {url}")
                    continue
                buf = bytearray()
                for chunk in response.iter_content(32768):
                    buf.extend(chunk)
                    if len(buf) > MAX_BYTES:
                        raise ValueError("HTML page exceeds 2 MB")
                response.encoding = response.encoding or "utf-8"
                html = bytes(buf).decode(response.encoding, errors="replace")
            title, content, links = extract(html, url)
            pages[url] = (title, content)
            if depth < depth_limit:
                for link in links:
                    if urlsplit(link).netloc == origin and link not in seen and not any(x == link for x, _ in queue):
                        queue.append((link, depth + 1))
        except (requests.RequestException, ValueError, OSError) as exc:
            errors.append(f"{url}: {exc}")
    return pages, errors


def save(site_id: int, pages: dict, errors: list[str], data: Path = DATA) -> int:
    if not pages:
        raise ValueError("No pages fetched; snapshot was not saved")
    now = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(database(data)) as db:
        run = db.execute("INSERT INTO runs(site_id,created_at,status,errors) VALUES (?,?,?,?)",
                         (site_id, now, "partial" if errors else "complete", json.dumps(errors))).lastrowid
        db.executemany("INSERT INTO pages(run_id,url,title,content,digest) VALUES (?,?,?,?,?)",
                       [(run, url, title, text, sha256(text.encode()).hexdigest())
                        for url, (title, text) in pages.items()])
    return run


def snapshot(site_id: int, url: str, limit: int, depth: int, data: Path = DATA) -> tuple[int, int, list[str]]:
    pages, errors = crawl(url, limit, depth)
    return save(site_id, pages, errors, data), len(pages), errors


def compare(old_id: int, new_id: int, data: Path = DATA) -> list[dict]:
    from .versions import effective_pages
    old = effective_pages(old_id,data)
    new = effective_pages(new_id,data)
    result = []
    for url in sorted(old.keys() | new.keys()):
        if url not in old:
            kind, title, before, after = "added", new[url][0], "", new[url][1]
        elif url not in new:
            kind, title, before, after = "missing", old[url][0], old[url][1], ""
        elif old[url][2] != new[url][2]:
            kind, title, before, after = "changed", new[url][0], old[url][1], new[url][1]
        else:
            continue
        diff = "\n".join(unified_diff(before.splitlines(), after.splitlines(),
                                       fromfile="before", tofile="after", lineterm=""))
        result.append({"url": url, "title": title, "kind": kind, "diff": diff})
    return result


def report(changes: list[dict], old_id: int, new_id: int) -> str:
    parts = ["<!doctype html><html lang='de'><meta charset='utf-8'>",
             "<title>WebSnapshot Änderungsbericht</title>",
             "<style>body{font:16px system-ui;max-width:1000px;margin:3rem auto;padding:0 1rem}"
             "section{border-top:1px solid #aaa;padding:1rem 0}"
             "pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f5f5f5;padding:1rem}</style>",
             f"<h1>Änderungsbericht</h1><p>Snapshots {old_id} → {new_id}</p>",
             "<p>Fehlende Seiten sind nicht als gelöscht bestätigt.</p>"]
    for c in changes:
        parts.append(f"<section><h2>{escape(c['kind'])}: {escape(c['title'])}</h2>"
                     f"<p><a href='{escape(c['url'], quote=True)}'>{escape(c['url'])}</a></p>"
                     f"<pre>{escape(c['diff'])}</pre></section>")
    return "".join(parts) + "</html>"
