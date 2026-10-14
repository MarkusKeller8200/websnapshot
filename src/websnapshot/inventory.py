"""Enhanced discovery, inventory and local management for WebSnapshot 0.2."""
from __future__ import annotations
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
import ipaddress
import json
import socket
import sqlite3
from urllib.parse import urljoin, urlsplit
from urllib.robotparser import RobotFileParser
import xml.etree.ElementTree as ET
import requests
from bs4 import BeautifulSoup
from .core import DATA, MAX_BYTES, AGENT, check_public, database, extract, normalize_url, save
from .documents import inventory_documents
from .versions import latest_run, effective_pages, save_partial, mark_full, kind
from .settings import get as get_capture
from hashlib import sha256
from .diagnostics import canonical, path_key, MAX_DISCOVERED, MAX_PER_PATH, MAX_PER_PAGE, record, record_quality, duplicate_groups


def remove_site(site_id: int, delete_history: bool = False, data: Path = DATA) -> None:
    """Remove a configured website. Historical snapshots are retained unless requested."""
    with sqlite3.connect(database(data)) as db:
        if delete_history:
            ids = [row[0] for row in db.execute("SELECT id FROM runs WHERE site_id=?", (site_id,))]
            db.executemany("DELETE FROM pages WHERE run_id=?", [(i,) for i in ids])
            db.execute("DELETE FROM runs WHERE site_id=?", (site_id,))
        db.execute("DELETE FROM sites WHERE id=?", (site_id,))


def _fetch(session: requests.Session, url: str, max_bytes: int = MAX_BYTES) -> tuple[bytes, str]:
    check_public(url)
    with session.get(url, timeout=(5, 20), stream=True, allow_redirects=False) as res:
        if res.is_redirect:
            raise ValueError("Weiterleitung nicht verfolgt")
        res.raise_for_status()
        kind = res.headers.get("Content-Type", "").lower()
        content = bytearray()
        for chunk in res.iter_content(32768):
            content.extend(chunk)
            if len(content) > max_bytes:
                raise ValueError("Maximale Antwortgrösse überschritten")
        return bytes(content), kind


def discover_and_snapshot(site_id: int, start: str, limit: int = 1000,
                          data: Path = DATA, progress=None, snapshot_kind: str = 'full') -> tuple[int, dict]:
    """Discover sitemap and HTML links; stop at transparent safety limits.

    All recorded URLs belong to the same network location, redirects are not followed.
    """
    from time import monotonic
    beginning = monotonic()
    def emit(**extra):
        if progress:
            current = dict(elapsed=round(monotonic()-beginning, 1), pages=len(pages),
                documents=len(docs), visited=len(visited), discovered=len(found),
                snapshot_kind=snapshot_kind, total_urls=len(baseline) if parent_id else None,
                changed=sum(1 for u,(_,content) in pages.items() if u not in baseline or
                    sha256(content.encode()).hexdigest()!=baseline[u][2]) if parent_id else 0,
                baseline_id=parent_id, full_baseline_id=full_id,
                changed_since_full=sum(1 for u,(_,content) in pages.items() if
                    u not in full_baseline or sha256(content.encode()).hexdigest()!=full_baseline[u][2]) if parent_id else 0)
            if parent_id:
                current['percent']=round(100*min(len(visited),len(baseline))/max(len(baseline),1),1)
            current.update(extra)
            progress(**current)
    if snapshot_kind not in ('full','partial'):
        raise ValueError('Ungültiger Snapshottyp')
    start = normalize_url(start)
    check_public(start)
    host = urlsplit(start).netloc
    origin = urlsplit(start).scheme + "://" + host
    session = requests.Session()
    session.headers["User-Agent"] = AGENT
    robot = RobotFileParser()
    robot.set_url(origin + "/robots.txt")
    robots_loaded = False
    try:
        # RobotFileParser.read does not expose a bounded timeout; use requests instead.
        raw, _ = _fetch(session, origin + "/robots.txt", 200_000)
        robot.parse(raw.decode("utf-8", "replace").splitlines())
        robots_loaded = True
    except (requests.RequestException, ValueError, OSError):
        pass
    parent_id = latest_run(site_id,data) if snapshot_kind == 'partial' else None
    if snapshot_kind == 'partial' and parent_id is None:
        raise ValueError('Für Partial-Snapshots wird ein Baseline-Snapshot benötigt')
    baseline = effective_pages(parent_id,data) if parent_id else {}
    full_id = parent_id
    if parent_id:
        while kind(full_id,data)[1] is not None:
            full_id=kind(full_id,data)[1]
    full_baseline=effective_pages(full_id,data) if full_id else {}
    queue = deque(baseline.keys()) if parent_id else deque([start])
    queued = set(queue) if parent_id else {start}
    visited = set()
    sitemap_queue = deque() if parent_id else deque([origin + '/sitemap.xml'])
    sitemap_seen = set()
    errors = []
    docs = set()
    found = set(queued)
    url_records = {u: ('baseline' if parent_id else 'start','queued','') for u in queued}
    path_counts = {}
    for u in queued:
        key=path_key(u)
        path_counts[key]=path_counts.get(key,0)+1
    truncated=False
    def enqueue(link, source):
        nonlocal truncated, skipped
        try:
            link=canonical(link)
            if urlsplit(link).netloc!=host or link in queued:
                return
            if len(queued)>=MAX_DISCOVERED:
                truncated=True
                skipped+=1
                return
            key=path_key(link)
            if path_counts.get(key,0)>=MAX_PER_PATH:
                skipped+=1
                truncated=True
                return
            queued.add(link)
            found.add(link)
            path_counts[key]=path_counts.get(key,0)+1
            url_records[link]=(source,'queued','')
            queue.append(link)
        except (ValueError,TypeError):
            skipped+=1
    skipped = 0
    pages = {}
    sitemap_urls = []
    renderer = None
    try:
        if get_capture(site_id,data)['mode'] == 'browser':
            from .browser import BrowserRenderer
            renderer = BrowserRenderer(start,get_capture(site_id,data))
    except Exception:
        raise
    emit(phase='Sitemaps prüfen')
    if robots_loaded:
        for line in raw.decode("utf-8", "replace").splitlines():
            if line.lower().startswith("sitemap:"):
                sitemap_queue.append(line.split(":", 1)[1].strip())
    while sitemap_queue and len(sitemap_seen) < 25 and len(found) < MAX_DISCOVERED:
        sm = sitemap_queue.popleft()
        try:
            sm = normalize_url(sm)
            if urlsplit(sm).netloc != host or sm in sitemap_seen:
                continue
            sitemap_seen.add(sm)
            rawxml, _ = _fetch(session, sm, 4_000_000)
            root = ET.fromstring(rawxml)
            for node in root.iter():
                if node.tag.rsplit("}", 1)[-1] != "loc" or not node.text:
                    continue
                link = normalize_url(node.text)
                if urlsplit(link).netloc != host:
                    continue
                if root.tag.rsplit("}", 1)[-1] == "sitemapindex":
                    if len(sitemap_seen) + len(sitemap_queue) < 25:
                        sitemap_queue.append(link)
                else:
                    sitemap_urls.append(link)
        except (requests.RequestException, ValueError, ET.ParseError, OSError):
            errors.append("Sitemap nicht lesbar: " + sm)
    for link in sitemap_urls:
        enqueue(link,'sitemap')
    emit(phase='Seiten durchsuchen')
    while queue and len(visited) < limit:
        url = queue.popleft()
        if url in visited:
            continue
        visited.add(url)
        url_records[url]=(url_records.get(url,('link','',''))[0],'visited','')
        if urlsplit(url).path.lower().endswith((".pdf", ".docx", ".doc")):
            docs.add(url)
            url_records[url]=(url_records[url][0],'document','')
            emit(phase="Dokument gefunden")
            continue
        try:
            if robots_loaded and not robot.can_fetch(AGENT, url):
                skipped += 1
                url_records[url]=(url_records[url][0],'excluded','robots.txt')
                continue
            if renderer and not urlsplit(url).path.lower().endswith((".pdf",".doc",".docx")):
                try:
                    title, content, links = renderer.fetch(url)
                except Exception as exc:
                    raise ValueError(f"Browser konnte Seite nicht erfassen: {exc}") from exc
                pages[url] = (title,content)
                url_records[url]=(url_records[url][0],'archived','')
                if not parent_id:
                    for link in links[:MAX_PER_PAGE]:
                        enqueue(link,'browser-link')
                    if len(links)>MAX_PER_PAGE:
                        truncated=True
                emit(phase="Browser-Erfassung")
                continue
            body, kind = _fetch(session, url)
            if "text/html" not in kind:
                if "pdf" in kind or "msword" in kind or "wordprocessingml" in kind:
                    docs.add(url)
                    url_records[url]=(url_records[url][0],"document","")
                else:
                    skipped += 1
                    url_records[url]=(url_records[url][0],"excluded","not-html")
                continue
            html = body.decode("utf-8", "replace")
            title, content, links = extract(html, url)
            pages[url] = (title, content)
            url_records[url]=(url_records[url][0],"archived","")
            for link in (links[:MAX_PER_PAGE] if not parent_id else []):
                enqueue(link,"html-link")
            if not parent_id and len(links)>MAX_PER_PAGE:
                truncated=True
        except (requests.RequestException, ValueError, OSError) as exc:
            errors.append(f"{url}: {exc}")
            url_records[url]=(url_records[url][0],"failed",str(exc)[:120])
        emit(phase="Seiten durchsuchen")
    remaining = len(queue)
    if remaining:
        errors.append(f"Schutzlimit erreicht: {remaining} URLs noch offen")
    if truncated:
        errors.append("Discovery-Schutzlimit erreicht: weitere URL-Varianten ausgeschlossen")
    if renderer:
        renderer.close()
    if parent_id:
        run_id, changed = save_partial(site_id,pages,errors,parent_id,data)
    else:
        run_id = save(site_id, pages, errors, data)
        mark_full(run_id,data)
        changed = len(pages)
    emit(phase="Dokument-Metadaten prüfen")
    inventory_documents(run_id, site_id, docs, session, data, progress=lambda **kw: emit(phase="Dokument-Metadaten prüfen", **kw))
    with sqlite3.connect(database(data)) as db:
        db.execute("""CREATE TABLE IF NOT EXISTS inventory (
            run_id INTEGER PRIMARY KEY, discovered INTEGER, documents INTEGER,
            visited INTEGER, skipped INTEGER, pending INTEGER, sitemap_count INTEGER)""")
        db.execute("INSERT INTO inventory VALUES (?,?,?,?,?,?,?)",
                   (run_id, len(found), len(docs), len(visited), skipped,
                    remaining, len(sitemap_seen)))
    record(run_id,url_records,data)
    record_quality(run_id,dict(discovered=len(found),visited=len(visited),archived=len(pages),
        documents=len(docs),pending=remaining,skipped=skipped,errors=len(errors),
        duplicate_content=duplicate_groups(pages),truncated=int(truncated or remaining>0),
        warning="Unvollständig" if truncated or remaining or errors else "Abgeschlossen (bekannte URLs)"),data)
    emit(phase="Fertig", changed=changed, percent=100 if parent_id and remaining == 0 else round(100*len(visited)/max(len(baseline),1),1) if parent_id else None)
    return run_id, {"snapshot_kind":snapshot_kind, "full_baseline_id":full_id,
                    "changed_since_full":sum(1 for u,(_,content) in pages.items() if u not in full_baseline or sha256(content.encode()).hexdigest()!=full_baseline[u][2]) if parent_id else 0,
                    "discovered":len(found), "pages":len(pages), "documents":len(docs),
                    "visited":len(visited), "skipped":skipped, "pending":remaining,
                    "sitemaps":len(sitemap_seen), "changed":changed, "errors":errors}


def storage_bytes(data: Path = DATA) -> int:
    if not data.exists():
        return 0
    return sum(p.stat().st_size for p in data.rglob("*") if p.is_file())


def dashboard(data: Path = DATA) -> list[dict]:
    with sqlite3.connect(database(data)) as db:
        db.execute("""CREATE TABLE IF NOT EXISTS inventory (
            run_id INTEGER PRIMARY KEY, discovered INTEGER, documents INTEGER,
            visited INTEGER, skipped INTEGER, pending INTEGER, sitemap_count INTEGER)""")
        entries = db.execute("""
            SELECT s.id, s.url, COUNT(r.id), MIN(r.created_at), MAX(r.created_at)
            FROM sites s LEFT JOIN runs r ON s.id=r.site_id GROUP BY s.id ORDER BY s.id DESC
        """).fetchall()
        result = []
        for site_id, url, count, oldest, newest in entries:
            latest = db.execute("SELECT id FROM runs WHERE site_id=? ORDER BY id DESC LIMIT 1",
                                (site_id,)).fetchone()
            page_count = document_count = discovered = pending = 0
            if latest:
                page_count = len(effective_pages(latest[0],data))
                inv = db.execute("SELECT discovered,documents,pending FROM inventory WHERE run_id=?",
                                 latest).fetchone()
                if inv:
                    discovered, document_count, pending = inv
            # Estimate stored text size per site; disk-wide SQLite overhead is reported separately.
            total = db.execute("""SELECT COALESCE(SUM(LENGTH(CAST(p.content AS BLOB))),0)
                FROM pages p JOIN runs r ON p.run_id=r.id WHERE r.site_id=?""", (site_id,)).fetchone()[0]
            age = ((datetime.now(timezone.utc) - datetime.fromisoformat(oldest)).days
                   if oldest else None)
            result.append(dict(id=site_id, url=url, snapshots=count, oldest=oldest,
                               newest=newest, oldest_age=age, pages=page_count,
                               documents=document_count, discovered=discovered,
                               pending=pending, content_bytes=total))
        return result
