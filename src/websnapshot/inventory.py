"""Enhanced discovery, inventory and local management for WebSnapshot 0.2."""
from __future__ import annotations
from collections import deque
from concurrent.futures import ThreadPoolExecutor
import threading
from time import perf_counter
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
from .document_metadata import save_references
from .doclinks import related_document
from .versions import latest_run, effective_pages, save_partial, mark_full, kind
from .settings import get as get_capture
from .crawl_scope import eligible_link, within_scope, is_document, effective_scope
from .global_settings import get as get_global
from .performance import Timings, save as save_performance
from .link_exclusions import LinkExclusionJournal
from .url_exclusions import parse_excludes, excluded_by
from .path_exclusion_audit import ExclusionStats
from hashlib import sha256
from .diagnostics import canonical, path_key, MAX_DISCOVERED, MAX_PER_PATH, MAX_PER_PAGE, record, record_quality, duplicate_groups


def remove_site(site_id: int, delete_history: bool = False, data: Path = DATA) -> None:
    """Remove a configured website. Historical snapshots are retained unless requested."""
    with sqlite3.connect(database(data)) as db:
        if delete_history:
            ids = [row[0] for row in db.execute("SELECT id FROM runs WHERE site_id=?", (site_id,))]
            for table in ("pages","documents","downloads","inventory","crawl_urls",
                          "crawl_quality","crawl_performance","document_links","document_referrers",
                          "document_properties","crawl_link_exclusions","crawl_path_exclusions","snapshot_meta"):
                exists=db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",(table,)).fetchone()
                if exists:
                    db.executemany(f"DELETE FROM {table} WHERE run_id=?",[(i,) for i in ids])
            db.execute("DELETE FROM runs WHERE site_id=?", (site_id,))
        db.execute("DELETE FROM sites WHERE id=?", (site_id,))


def _fetch(session: requests.Session, url: str, max_bytes: int = MAX_BYTES,
           timeout: float = 3.0) -> tuple[bytes, str]:
    check_public(url)
    with session.get(url, timeout=(timeout, timeout), stream=True, allow_redirects=False) as res:
        if res.is_redirect:
            raise ValueError("Weiterleitung nicht verfolgt")
        res.raise_for_status()
        kind = res.headers.get("Content-Type", "").lower()
        if "text/html" not in kind and "xml" not in kind and "text/plain" not in kind:
            return b"",kind
        content = bytearray()
        for chunk in res.iter_content(32768):
            content.extend(chunk)
            if len(content) > max_bytes:
                raise ValueError("Maximale Antwortgrösse überschritten")
        return bytes(content), kind


def discover_and_snapshot(site_id: int, start: str, limit: int = 2000,
                          data: Path = DATA, progress=None, snapshot_kind: str = 'full',
                          config: dict | None = None) -> tuple[int, dict]:
    """Discover sitemap and HTML links; stop at transparent safety limits.

    All recorded URLs belong to the same network location, redirects are not followed.
    """
    from time import monotonic
    beginning = monotonic()
    config = dict(config) if config is not None else get_global(data)
    site_profile=get_capture(site_id,data)
    scope_mode=config.get("crawl_scope",site_profile["crawl_scope"])
    exclude_paths=parse_excludes(config.get("exclude_paths",site_profile["exclude_paths"]))
    excluded_stats=ExclusionStats(exclude_paths)
    effective_mode = effective_scope(start,scope_mode)
    discovery_limit = int(config.get("discovery_limit",200000))
    page_timeout = float(config.get("page_timeout",3.0))
    http_workers = max(1,min(10,int(config.get("http_workers",3))))
    links_per_page = max(1,min(10000,int(config.get("links_per_page",1000))))
    timings = Timings()
    static_pages = browser_static_pages = browser_dynamic_pages = browser_unknown_pages = timeouts = 0
    changed_count = changed_from_full = 0
    last_emit = 0.0
    last_phase = None
    def emit(**extra):
        nonlocal last_emit,last_phase
        phase=extra.get("phase")
        now=monotonic()
        if progress and (phase!=last_phase or now-last_emit>=0.75
                         or phase=="Fertig"):
            last_emit=now
            last_phase=phase
            current = dict(elapsed=round(monotonic()-beginning, 1), pages=len(pages),
                documents=len(docs), visited=len(visited), discovered=len(found),
                visit_limit=limit, discovery_limit=discovery_limit,
                page_timeout=page_timeout, http_workers=http_workers,
                links_per_page=links_per_page,
                crawl_scope=effective_mode,scope_excluded=scope_excluded,
                exclude_paths=exclude_paths, path_excluded=excluded_stats.total,
                performance=timings.summary(),
                static_pages=static_pages,
                browser_static_pages=browser_static_pages,
                browser_dynamic_pages=browser_dynamic_pages,
                browser_unknown_pages=browser_unknown_pages,
                timeouts=timeouts,
                pending=len(queue), skipped=skipped,
                excluded_limits=dict(limit_exclusions),
                limit_warnings=limit_warnings(),
                snapshot_kind=snapshot_kind, total_urls=len(baseline) if parent_id else None,
                changed=changed_count,
                baseline_id=parent_id, full_baseline_id=full_id,
                changed_since_full=changed_from_full)
            if parent_id:
                current['percent']=round(100*min(len(visited),len(baseline))/max(len(baseline),1),1)
            current.update(extra)
            progress(**current)
    if snapshot_kind not in ('full','partial'):
        raise ValueError('Ungültiger Snapshottyp')
    start = normalize_url(start)
    if excluded_by(start,exclude_paths):
        raise ValueError("Die Startadresse ist durch die Ausschlussliste gesperrt.")
    check_public(start)
    host = urlsplit(start).netloc
    origin = urlsplit(start).scheme + "://" + host
    session = requests.Session()
    session.headers["User-Agent"] = AGENT
    robot = RobotFileParser()
    robot.set_url(origin + "/robots.txt")
    robots_loaded = False
    discovery_started=perf_counter()
    robots_started=perf_counter()
    try:
        # RobotFileParser.read does not expose a bounded timeout; use requests instead.
        raw, _ = _fetch(session, origin + "/robots.txt", 200_000, page_timeout)
        robot.parse(raw.decode("utf-8", "replace").splitlines())
        robots_loaded = True
    except (requests.RequestException, ValueError, OSError) as exc:
        if isinstance(exc,requests.Timeout):
            timeouts+=1
    finally:
        timings.observe("robots_fetch",perf_counter()-robots_started,origin+"/robots.txt")
    parent_id = latest_run(site_id,data) if snapshot_kind == 'partial' else None
    if snapshot_kind == 'partial' and parent_id is None:
        raise ValueError('Für Partial-Snapshots wird ein Baseline-Snapshot benötigt')
    if parent_id is not None and effective_mode=="path":
        # Delta snapshots inherit all pages from their parent. A former
        # domain-wide baseline would silently reintroduce out-of-scope pages.
        with sqlite3.connect(database(data)) as db:
            exists=db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='jobs'").fetchone()
            prior=db.execute("SELECT progress FROM jobs WHERE run_id=? ORDER BY id DESC LIMIT 1",
                             (parent_id,)).fetchone() if exists else None
        previous_scope=(json.loads(prior[0] or "{}").get("crawl_scope")
                        if prior else None)
        if previous_scope!="path":
            raise ValueError("Für diesen Unterbereich zuerst einen neuen Full-Snapshot "
                             "erstellen: Der Vorgänger hat keinen bestätigten "
                             "passenden Erfassungsbereich.")
    if parent_id is not None and exclude_paths:
        # A delta inherits old pages; it cannot remove previously included
        # pages that a newly added path rule would exclude.
        with sqlite3.connect(database(data)) as db:
            has_jobs=db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='jobs'").fetchone()
            prior_row=db.execute("SELECT progress FROM jobs WHERE run_id=? ORDER BY id DESC LIMIT 1",
                                 (parent_id,)).fetchone() if has_jobs else None
        previous_rules=parse_excludes(
            json.loads(prior_row[0] or "{}").get("exclude_paths",[])
            if prior_row else [])
        if previous_rules!=exclude_paths:
            raise ValueError("Ausschlussliste geändert: Bitte zuerst einen neuen "
                             "Full-Snapshot erstellen, damit keine ausgeschlossenen "
                             "Seiten aus dem alten Snapshot geerbt werden.")
    baseline = effective_pages(parent_id,data) if parent_id else {}
    full_id = parent_id
    if parent_id:
        while kind(full_id,data)[1] is not None:
            full_id=kind(full_id,data)[1]
    full_baseline=effective_pages(full_id,data) if full_id else {}
    def register_change(url,content):
        nonlocal changed_count,changed_from_full
        if parent_id:
            digest=sha256(content.encode()).hexdigest()
            if url not in baseline or digest!=baseline[url][2]:
                changed_count+=1
            if url not in full_baseline or digest!=full_baseline[url][2]:
                changed_from_full+=1
    queue = deque(baseline.keys()) if parent_id else deque([start])
    queued = set(queue) if parent_id else {start}
    visited = set()
    sitemap_queue = deque() if parent_id else deque([origin + '/sitemap.xml'])
    sitemap_seen = set()
    errors = []
    docs = set()
    document_references = {}
    link_audit = LinkExclusionJournal()
    found = set(queued)
    url_records = {u: ('baseline' if parent_id else 'start','queued','') for u in queued}
    path_counts = {}
    for u in queued:
        key=path_key(u)
        path_counts[key]=path_counts.get(key,0)+1
    truncated=False
    scope_excluded=0
    limit_exclusions={"discovery":0,"path_variants":0,"page_links":0}
    def limit_warnings():
        warnings=[]
        if len(found)>=discovery_limit or limit_exclusions["discovery"]:
            warnings.append(f"Discovery-Limit ({discovery_limit}) erreicht: {limit_exclusions['discovery']} URL-Kandidaten abgewiesen")
        if limit_exclusions["path_variants"]:
            warnings.append(f"Pfadvarianten-Limit ({MAX_PER_PATH}) erreicht: {limit_exclusions['path_variants']} URL-Kandidaten abgewiesen")
        if limit_exclusions["page_links"]:
            warnings.append(f"Links-pro-Seite-Limit ({links_per_page}) erreicht: {limit_exclusions['page_links']} Links nicht weiterverfolgt")
        if len(visited)>=limit and queue:
            warnings.append(f"Besuchslimit ({limit}) erreicht: {len(queue)} URLs offen")
        return warnings
    def enqueue(link, source, source_page=None):
        nonlocal truncated, skipped, scope_excluded
        try:
            link=canonical(link)
            direct=source in ("html-link","browser-link")
            related=related_document(link,start) and direct
            if not (eligible_link(link,start,effective_mode,directly_linked=direct) or related):
                if urlsplit(link).netloc==host and not within_scope(link,start,effective_mode):
                    scope_excluded+=1
                return
            excluded_rule=excluded_by(link,exclude_paths)
            if excluded_rule:
                excluded_stats.record(excluded_rule,link)
                return
            if is_document(link) and source_page:
                document_references.setdefault(link,set()).add((source_page,source))
            if link in queued or link in docs:
                return
            # Recognise linked documents immediately. They do not consume the
            # HTML page-visit limit, even when hosted in a shared asset folder.
            if is_document(link) and (related or urlsplit(link).netloc==host):
                if len(found)>=discovery_limit:
                    limit_exclusions["discovery"]+=1
                    truncated=True
                    skipped+=1
                    return
                docs.add(link)
                found.add(link)
                url_records[link]=(source,"document",
                                   "Zugehöriger Dokument-Host" if related
                                   else "Verlinktes Dokument")
                return
            if len(found)>=discovery_limit:
                limit_exclusions["discovery"]+=1
                truncated=True
                skipped+=1
                return
            key=path_key(link)
            if path_counts.get(key,0)>=MAX_PER_PATH:
                limit_exclusions["path_variants"]+=1
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
    capture_settings=get_capture(site_id,data)
    try:
        if capture_settings['mode'] == 'browser':
            from .browser import BrowserRenderer
            renderer = BrowserRenderer(start,{**capture_settings,"page_timeout":page_timeout})
    except Exception:
        raise
    emit(phase='Sitemaps prüfen')
    if robots_loaded:
        for line in raw.decode("utf-8", "replace").splitlines():
            if line.lower().startswith("sitemap:"):
                sitemap_queue.append(line.split(":", 1)[1].strip())
    while sitemap_queue and len(sitemap_seen) < 25 and len(found) < discovery_limit:
        sm = sitemap_queue.popleft()
        sitemap_started=perf_counter()
        try:
            sm = normalize_url(sm)
            if urlsplit(sm).netloc != host or sm in sitemap_seen:
                continue
            sitemap_seen.add(sm)
            excluded_rule=excluded_by(sm,exclude_paths)
            if excluded_rule:
                excluded_stats.record(excluded_rule,sm)
                continue
            rawxml, _ = _fetch(session, sm, 4_000_000, page_timeout)
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
                    # Avoid enqueuing another department from a domain-wide
                    # sitemap; only pages/docs within the logical subtree.
                    if within_scope(link,start,effective_mode):
                        excluded_rule=excluded_by(link,exclude_paths)
                        if excluded_rule:
                            excluded_stats.record(excluded_rule,link)
                        else:
                            sitemap_urls.append((link,sm))
                    else:
                        scope_excluded+=1
        except (requests.RequestException, ValueError, ET.ParseError, OSError) as exc:
            errors.append("Sitemap nicht lesbar: " + sm)
            if isinstance(exc,requests.Timeout):
                timeouts+=1
        finally:
            timings.observe("sitemap_fetch",perf_counter()-sitemap_started,sm)
            emit(phase="Sitemaps prüfen")
    for link,sm_source in sitemap_urls:
        enqueue(link,'sitemap',sm_source)
    timings.observe("discovery_initial",perf_counter()-discovery_started,origin)
    emit(phase='Seiten durchsuchen')
    worker_state=threading.local()
    def fetch_page(url):
        # A persistent Session per worker reuses TCP/TLS connections and never
        # shares a requests.Session across threads.
        started=perf_counter()
        client=getattr(worker_state,"client",None)
        if client is None:
            client=requests.Session()
            client.headers["User-Agent"]=AGENT
            worker_state.client=client
        try:
            result=_fetch(client,url,MAX_BYTES,page_timeout)
            return result,None,perf_counter()-started
        except (requests.RequestException,ValueError,OSError) as exc:
            return None,exc,perf_counter()-started

    with ThreadPoolExecutor(max_workers=1 if renderer else http_workers,
                            thread_name_prefix="websnapshot-fetch") as executor:
        while queue and len(visited) < limit:
            batch=[]
            while queue and len(visited)<limit and len(batch)<(1 if renderer else http_workers):
                url=queue.popleft()
                excluded_rule=excluded_by(url,exclude_paths)
                if excluded_rule:
                    excluded_stats.record(excluded_rule,url)
                    continue
                if url in visited:
                    continue
                visited.add(url)
                url_records[url]=(url_records.get(url,('link','',''))[0],'visited','')
                if urlsplit(url).path.lower().endswith((".pdf",".docx",".doc",".xlsx",".xls",".txt",".csv")):
                    docs.add(url)
                    url_records[url]=(url_records[url][0],"document","")
                    emit(phase="Dokument gefunden")
                    continue
                if robots_loaded and not robot.can_fetch(AGENT,url):
                    skipped+=1
                    url_records[url]=(url_records[url][0],"excluded","robots.txt")
                    emit(phase="robots.txt")
                    continue
                batch.append(url)
            if not batch:
                continue
            if renderer:
                url=batch[0]
                started=perf_counter()
                try:
                    title,content,links=renderer.fetch(url)
                    timings.observe("page_fetch",perf_counter()-started,url)
                    pages[url]=(title,content)
                    register_change(url,content)
                    url_records[url]=(url_records[url][0],"archived","")
                    page_kind=getattr(renderer,"last_page_kind","browser_unknown")
                    if page_kind=="browser_dynamic":
                        browser_dynamic_pages+=1
                    elif page_kind=="browser_static":
                        browser_static_pages+=1
                    else:
                        browser_unknown_pages+=1
                    if not parent_id:
                        discovery_tick=perf_counter()
                        links_allowed=[link for link in links if
                            eligible_link(link,start,effective_mode) or related_document(link,start)]
                        scope_excluded+=sum(1 for link in links if
                            urlsplit(link).netloc==host and
                            not eligible_link(link,start,effective_mode))
                        links=[]
                        for link in links_allowed:
                            excluded_rule=excluded_by(link,exclude_paths)
                            if excluded_rule:
                                excluded_stats.record(excluded_rule,link)
                            else:
                                links.append(link)
                        for link in links[:links_per_page]:
                            enqueue(link,"browser-link",url)
                        if len(links)>links_per_page:
                            limit_exclusions["page_links"]+=len(links)-links_per_page
                            link_audit.add(url,links[links_per_page:])
                            truncated=True
                        timings.observe("discovery_links",perf_counter()-discovery_tick,url)
                except (requests.RequestException,ValueError,OSError,Exception) as exc:
                    timings.observe("page_fetch",perf_counter()-started,url)
                    if "timeout" in str(exc).lower():
                        timeouts+=1
                    errors.append(f"{url}: {exc}")
                    url_records[url]=(url_records[url][0],"failed",str(exc)[:120])
                emit(phase="Browser-Erfassung")
                continue
            outputs=list(executor.map(fetch_page,batch))
            for url,(reply,error,elapsed) in zip(batch,outputs):
                timings.observe("page_fetch",elapsed,url)
                if error is not None:
                    if isinstance(error,requests.Timeout):
                        timeouts+=1
                    errors.append(f"{url}: {error}")
                    url_records[url]=(url_records[url][0],"failed",str(error)[:120])
                    emit(phase="Seiten durchsuchen")
                    continue
                body,kind=reply
                if "text/html" not in kind:
                    if any(k in kind for k in ("pdf","msword","wordprocessingml","spreadsheetml","vnd.ms-excel","text/plain","text/csv","application/csv")):
                        docs.add(url)
                        url_records[url]=(url_records[url][0],"document","")
                    else:
                        skipped+=1
                        url_records[url]=(url_records[url][0],"excluded","not-html")
                    emit(phase="Seiten durchsuchen")
                    continue
                try:
                    title,content,links=extract(body.decode("utf-8","replace"),url)
                    pages[url]=(title,content)
                    register_change(url,content)
                    static_pages+=1
                    url_records[url]=(url_records[url][0],"archived","")
                    if not parent_id:
                        discovery_tick=perf_counter()
                        links_allowed=[link for link in links if
                            eligible_link(link,start,effective_mode) or related_document(link,start)]
                        scope_excluded+=sum(1 for link in links if
                            urlsplit(link).netloc==host and
                            not eligible_link(link,start,effective_mode))
                        links=[]
                        for link in links_allowed:
                            excluded_rule=excluded_by(link,exclude_paths)
                            if excluded_rule:
                                excluded_stats.record(excluded_rule,link)
                            else:
                                links.append(link)
                        for link in links[:links_per_page]:
                            enqueue(link,"html-link",url)
                        if len(links)>links_per_page:
                            limit_exclusions["page_links"]+=len(links)-links_per_page
                            link_audit.add(url,links[links_per_page:])
                            truncated=True
                        timings.observe("discovery_links",perf_counter()-discovery_tick,url)
                except (ValueError,TypeError) as exc:
                    errors.append(f"{url}: {exc}")
                    url_records[url]=(url_records[url][0],"failed",str(exc)[:120])
                emit(phase="Seiten durchsuchen")

    remaining = len(queue)
    if remaining:
        errors.append(f"Schutzlimit erreicht: {remaining} URLs noch offen")
    for warning in limit_warnings():
        if not warning.startswith("Besuchslimit"):
            errors.append(warning)
    if renderer:
        renderer.close()
    emit(phase="Snapshot speichern")
    save_tick=perf_counter()
    if parent_id:
        run_id, changed = save_partial(site_id,pages,errors,parent_id,data)
    else:
        run_id = save(site_id, pages, errors, data)
        mark_full(run_id,data)
        changed = len(pages)
    timings.observe("snapshot_save",perf_counter()-save_tick,"SQLite")
    emit(phase="Dokument-Metadaten prüfen")
    metadata_started=perf_counter()
    inventory_documents(run_id, site_id, docs, session, data, progress=lambda **kw: emit(phase="Dokument-Metadaten prüfen", **kw))
    timings.observe("document_metadata",perf_counter()-metadata_started,"HEAD")
    save_references(run_id,document_references,data)
    emit(phase="Diagnose speichern")
    diag_started=perf_counter()
    with sqlite3.connect(database(data)) as db:
        db.execute("""CREATE TABLE IF NOT EXISTS inventory (
            run_id INTEGER PRIMARY KEY, discovered INTEGER, documents INTEGER,
            visited INTEGER, skipped INTEGER, pending INTEGER, sitemap_count INTEGER)""")
        db.execute("INSERT INTO inventory VALUES (?,?,?,?,?,?,?)",
                   (run_id, len(found), len(docs), len(visited), skipped,
                    remaining, len(sitemap_seen)))
    record(run_id,url_records,data)
    link_audit.persist(run_id,data)
    excluded_stats.save(run_id,data)
    record_quality(run_id,dict(discovered=len(found),visited=len(visited),archived=len(pages),
        documents=len(docs),pending=remaining,skipped=skipped,errors=len(errors),
        duplicate_content=duplicate_groups(pages),truncated=int(truncated or remaining>0),
        warning="Unvollständig" if truncated or remaining or errors else "Abgeschlossen (bekannte URLs)"),data)
    timings.observe("diagnostic_save",perf_counter()-diag_started,"SQLite")
    save_performance(run_id,timings,static_pages=static_pages,
                     browser_static_pages=browser_static_pages,
                     browser_dynamic_pages=browser_dynamic_pages,
                     browser_unknown_pages=browser_unknown_pages,
                     timeouts=timeouts,data=data)
    emit(phase="Fertig",changed=changed,percent=100 if parent_id and remaining == 0 else round(100*len(visited)/max(len(baseline),1),1) if parent_id else None)
    return run_id, {"snapshot_kind":snapshot_kind, "full_baseline_id":full_id,
                    "crawl_scope":effective_mode,"scope_excluded":scope_excluded,
                    "exclude_paths":exclude_paths,"path_excluded":excluded_stats.total,
                    "changed_since_full":changed_from_full,
                    "discovered":len(found), "pages":len(pages), "documents":len(docs),
                    "visited":len(visited), "skipped":skipped, "pending":remaining,
                    "excluded_limits":dict(limit_exclusions), "limit_warnings":limit_warnings(),
                    "sitemaps":len(sitemap_seen), "changed":changed, "errors":errors,
                    "discovery_limit":discovery_limit,"page_timeout":page_timeout,
                    "http_workers":http_workers,"links_per_page":links_per_page,
                    "excluded_link_pages":len(link_audit.per_source),
                    "performance":timings.summary(),
                    "static_pages":static_pages,"browser_static_pages":browser_static_pages,
                    "browser_dynamic_pages":browser_dynamic_pages,
                    "browser_unknown_pages":browser_unknown_pages,"timeouts":timeouts}


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
