"""WebSnapshot: lokales Dashboard und manuell gestartete Website-Inventarisierung."""
import json
from concurrent.futures import ThreadPoolExecutor
from time import monotonic, sleep
from datetime import datetime
from pathlib import Path
import os
import subprocess
import sys
import streamlit as st

from websnapshot.core import DATA, add_site, sites, runs, compare, report
from websnapshot.inventory import dashboard, discover_and_snapshot, remove_site, storage_bytes
from websnapshot.documents import list_documents, download_selected
from websnapshot.document_metadata import probe_selected, list_references
from websnapshot.document_properties import display_properties
from websnapshot.jobs import launch, latest, running, recover_interrupted, request_cancel, snapshot_job
from websnapshot.job_logging import read as read_job_log, log_path
from websnapshot.diagnostics import summary
from websnapshot.link_exclusions import stats as excluded_link_stats, page as excluded_link_page, csv_page as excluded_link_csv_page
from websnapshot.settings import MODES, STATIC, get as get_capture, set_settings
from websnapshot.crawl_scope import SCOPES, effective_scope, logical_root
from websnapshot.versions import kind, effective_pages, effective_page_metadata, remove_snapshot
from urllib.parse import urlsplit
from hashlib import sha1
from websnapshot.document_selection import filter_documents, bulk_selection, merge_visible


from websnapshot.global_settings import get as get_global, save as save_global, VALID_HEIGHTS
from websnapshot.performance import get as get_performance
from websnapshot.table_layout import column_width, streamlit_columns
from websnapshot.sitemap_view import (tree_from_pages,visible_tree_rows,all_parent_ids,
    filtered_page_rows,export_csv,export_xlsx)
from websnapshot.ui_diff import comparison_html
from websnapshot.document_metadata import list_references, probe_selected
from websnapshot.document_properties import display_properties
from websnapshot.document_renamer import (get_profile, set_profile, RENAMED, ORIGINAL,
    CASE_MODES, filename_from_headers, build_filename, choose_date)

ROOT = Path(__file__).resolve().parents[2]
st.set_page_config(page_title="WebSnapshot", page_icon="📸", layout="wide",
                   initial_sidebar_state="expanded")
st.markdown("""
<style>
.block-container {
    max-width: 100% !important;
    padding-top: 3.7rem !important;
    padding-bottom: 1.5rem !important;
    padding-left: 1.6rem !important;
    padding-right: 1.6rem !important;
}
/* Streamlit determines sidebar width dynamically; avoid keeping 20rem reserved. */
[data-testid="stMain"] {min-width: 0 !important;}
/* The built-in control hides all icons, so the custom menu toggle handles
   expanded vs. compact navigation instead. */
[data-testid="stSidebarCollapseButton"],
[data-testid="stSidebarCollapsedControl"] {display:none !important;}
[data-testid="stVerticalBlock"] {gap: .65rem;}
[data-testid="stMetricValue"] {font-size: 1.5rem;}
/* Streamlit nests labels in a Markdown wrapper. Align the button AND its
   inner wrapper; otherwise full-width buttons still centre icons and text. */
[data-testid="stSidebar"] [data-testid="stButton"] {
    width: 100% !important;
}
[data-testid="stSidebar"] [data-testid="stButton"] > button,
[data-testid="stSidebar"] [data-testid="stButton"] button[data-testid^="stBaseButton"] {
    width: 100% !important;
    display: flex !important;
    justify-content: flex-start !important;
    align-items: center !important;
    text-align: left !important;
    padding-left: 0.85rem !important;
    padding-right: 0.65rem !important;
}
[data-testid="stSidebar"] [data-testid="stButton"] button [data-testid="stMarkdownContainer"],
[data-testid="stSidebar"] [data-testid="stButton"] button > div,
[data-testid="stSidebar"] [data-testid="stButton"] button > span {
    display: flex !important;
    flex: 1 1 auto !important;
    justify-content: flex-start !important;
    align-items: center !important;
    width: 100% !important;
    text-align: left !important;
    margin-left: 0 !important;
    margin-right: 0 !important;
}
[data-testid="stSidebar"] [data-testid="stButton"] button p,
[data-testid="stSidebar"] [data-testid="stButton"] button span {
    text-align: left !important;
    margin: 0 !important;
}
</style>
""", unsafe_allow_html=True)
st.markdown("## 📸 WebSnapshot")
st.caption("Website-Inventarisierung, Snapshots und Änderungsanalyse · v0.6.9")

NAV = [
    ("ÜBERSICHT", [
        ("Dashboard", "📊 Dashboard"),
        ("Websites verwalten", "🌐 Websites verwalten"),
    ]),
    ("SNAPSHOTS", [
        ("Snapshot starten", "📸 Snapshot starten"),
        ("Snapshot-Verwaltung", "🗂️ Snapshot-Verwaltung"),
    ]),
    ("AUSWERTUNG", [
        ("Änderungsvergleich", "🔍 Änderungsvergleich"),
        ("Dokumente", "📄 Dokumente herunterladen"),
        ("Sitemap", "🗺️ Sitemap"),
        ("Job-Protokolle", "📋 Job-Protokolle"),
    ]),
    ("SYSTEM", [
        ("Einstellungen", "⚙️ Einstellungen"),
        ("Updates", "🔄 Updates"),
    ]),
]
known_pages={ident for _, entries in NAV for ident,_ in entries}
if st.session_state.get("ws_page") not in known_pages:
    st.session_state["ws_page"] = "Dashboard"
current_page = st.session_state["ws_page"]
global_config = get_global()
site_options = dict(sites())
if st.session_state.get("active_site_id") not in site_options:
    st.session_state["active_site_id"] = next(iter(site_options), None)
active_site_id = st.session_state["active_site_id"]
if "ws_compact_nav" not in st.session_state:
    st.session_state["ws_compact_nav"] = False
compact_nav=bool(st.session_state["ws_compact_nav"])
if compact_nav:
    st.markdown("""<style>
    section[data-testid="stSidebar"] {
        width: 4.7rem !important;
        min-width: 4.7rem !important;
        max-width: 4.7rem !important;
        flex: 0 0 4.7rem !important;
    }
    section[data-testid="stSidebar"] [data-testid="stSidebarContent"] {
        padding-left: .3rem !important;
        padding-right: .3rem !important;
    }
    section[data-testid="stSidebar"] button {
        padding-left: .25rem !important;
        padding-right: .25rem !important;
        justify-content: center !important;
    }
    section[data-testid="stSidebar"] button [data-testid="stMarkdownContainer"] {
        justify-content: center !important;
    }
    </style>""",unsafe_allow_html=True)
with st.sidebar:
    if st.button("▶" if compact_nav else "◀ Menü einklappen",
                 key="ws_nav_toggle",use_container_width=True,
                 help="Menü ausklappen" if compact_nav else "Menü auf Symbole reduzieren"):
        st.session_state["ws_compact_nav"]=not compact_nav
        st.rerun()
    if not compact_nav:
        st.markdown("### 🧭 Navigation")
    for group,entries in NAV:
        if compact_nav:
            st.divider()
        else:
            st.caption(group)
        for page,label in entries:
            icon=label.split(" ",1)[0]
            if st.button(icon if compact_nav else label,
                         key="page_"+page,help=label if compact_nav else None,
                         type="primary" if page==current_page else "secondary",
                         use_container_width=True):
                st.session_state["ws_page"]=page
                st.rerun()
        if group=="ÜBERSICHT":
            if site_options:
                def site_label(sid):
                    address=site_options[sid]
                    parsed=urlsplit(address)
                    name=parsed.netloc+(parsed.path if parsed.path not in ("","/") else "")
                    return name[:65]+"…" if len(name)>66 else name
                if compact_nav:
                    with st.popover("🌐",help="Website auswählen",use_container_width=True):
                        chosen=st.selectbox("Website auswählen",
                            options=list(site_options),
                            index=list(site_options).index(active_site_id),
                            format_func=site_label,key="ws_site_compact")
                        if chosen!=active_site_id:
                            st.session_state["active_site_id"]=chosen
                            st.rerun()
                else:
                    chosen=st.selectbox("Website auswählen",
                        options=list(site_options),
                        index=list(site_options).index(active_site_id),
                        format_func=site_label,key="ws_site_dropdown")
                    if chosen!=active_site_id:
                        st.session_state["active_site_id"]=chosen
                        st.rerun()
            elif not compact_nav:
                st.caption("Noch keine Websites registriert.")
    if not compact_nav:
        st.caption("Mit dem Pfeilsymbol bleibt die Navigation als Icon-Leiste sichtbar.")


@st.fragment(run_every="2s")
def job_controls(site_id, url, limit, snap_kind):
    from datetime import timezone
    job = latest(site_id)
    active = bool(job and job["state"] in ("queued","running"))
    if job:
        info = json.loads(job["progress"] or "{}")
        start_time = datetime.fromisoformat(job["started_at"])
        end_time = datetime.fromisoformat(job["ended_at"]) if job["ended_at"] else datetime.now(timezone.utc)
        elapsed = max(0,int((end_time-start_time).total_seconds()))
        st.write(f"**Job #{job['id']} · {job['state']}**")
        last_activity=job.get("last_activity_at") or job.get("last_progress_at")
        if last_activity:
            idle=max(0,int((datetime.now(timezone.utc)-datetime.fromisoformat(last_activity)).total_seconds()))
            st.caption(f"Letzte Aktivität: {datetime.fromisoformat(last_activity).strftime('%d.%m. %H:%M:%S')} UTC · vor {idle}s")
            if active and idle >= 60:
                st.warning(f"Seit {idle} Sekunden kein Fortschritt. Möglicherweise langsame Anfrage oder blockierter Job; dies ist noch kein sicherer Absturznachweis.")
        with st.expander("Technisches Job-Protokoll", expanded=False):
            logfile=read_job_log(job["id"])
            st.code(logfile,language="text")
            if log_path(job["id"]).is_file():
                st.download_button("Logdatei herunterladen",data=logfile,
                    file_name=f"job_{job['id']}.log",mime="text/plain",
                    key=f"log_current_{site_id}_{job['id']}")
        col = st.columns(4)
        col[0].metric("Gestartet (UTC)",start_time.strftime("%d.%m. %H:%M"))
        col[1].metric("Laufzeit",f"{elapsed//60:02d}:{elapsed%60:02d}")
        col[2].metric("Seiten",info.get("pages",0))
        col[3].metric("Dokumente",info.get("documents",0))
        if info.get("snapshot_kind")=="partial":
            percent = float(info.get("percent",0) or 0)
            st.progress(min(1.0,max(0.0,percent/100)),text=f"{percent:.1f}% der bekannten URLs geprüft")
            x,y=st.columns(2)
            x.metric("Geänderte geprüfte Seiten zum Vorgänger",info.get("changed",0))
            y.metric("Geänderte geprüfte Seiten zur Full-Baseline",info.get("changed_since_full",0))
            st.caption(f"Vorgänger #{info.get('baseline_id','?')} · Full-Baseline #{info.get('full_baseline_id','?')} · nur erfolgreich geprüfte URLs")
        else:
            discovered=int(info.get("discovered",0) or 0)
            visited=int(info.get("visited",0) or 0)
            discovery_limit=int(info.get("discovery_limit",200000) or 200000)
            visit_limit=int(info.get("visit_limit",limit) or limit)
            st.caption(f"Phase: {info.get('phase','Wartet')} · "
                       f"{info.get('pending','—')} URLs in Warteschlange")
            bar_left,bar_right=st.columns(2)
            with bar_left:
                st.progress(min(1.,discovered/max(discovery_limit,1)),
                            text=f"Entdeckte URLs: {discovered:,} / {discovery_limit:,}".replace(",", "'"))
            with bar_right:
                st.progress(min(1.,visited/max(visit_limit,1)),
                            text=f"Besuchte URLs: {visited:,} / {visit_limit:,}".replace(",", "'"))
        perf=info.get("performance") or {}
        if perf:
            with st.expander("⏱️ Antwort- und Verarbeitungszeiten (live)",expanded=False):
                names={"discovery_initial":"Gesamte initiale Discovery",
                       "robots_fetch":"robots.txt abrufen",
                       "sitemap_fetch":"Sitemaps abrufen",
                       "discovery_links":"Link-Discovery",
                       "page_fetch":"Seitenabrufe",
                       "snapshot_save":"Snapshot speichern",
                       "document_metadata":"Dokument-Metadaten",
                       "diagnostic_save":"Diagnosedaten speichern"}
                timing_rows=[{"Phase":names.get(k,k),"Anzahl":v["count"],
                              "Minimum (ms)":v["min_ms"],
                              "Durchschnitt (ms)":v["avg_ms"],
                              "Maximum (ms)":v["max_ms"]}
                              for k,v in perf.items()]
                st.dataframe(timing_rows,hide_index=True,width="stretch",
                             column_config=streamlit_columns(timing_rows))
                st.caption(f"Statische HTML-Seiten: {info.get('static_pages',0)} · "
                           f"Browser ohne deutliche JS-Änderung: {info.get('browser_static_pages',0)} · "
                           f"Browser mit dynamischen Inhalten (Indiz): {info.get('browser_dynamic_pages',0)} · "
                           f"Unklar: {info.get('browser_unknown_pages',0)} · "
                           f"Timeouts: {info.get('timeouts',0)}")
        if info.get("crawl_scope")=="path":
            st.caption(f"Unterbereich aktiv · Ausserhalb des Bereichs verworfene "
                       f"URL-Kandidaten: {info.get('scope_excluded',0):,}".replace(",", "'"))
        warnings=info.get("limit_warnings",[])
        if warnings:
            st.warning("**Schutzlimit erreicht**\n\n" + "\n\n".join(
                f"• {warning}" for warning in warnings))
            exclusions=info.get("excluded_limits",{})
            if exclusions:
                st.caption("Abgewiesene URL-Kandidaten: "
                    f"{sum(int(v) for v in exclusions.values()):,}".replace(",", "'")
                    + " · Detailwerte werden im Job-Protokoll gespeichert.")
        if active:
            st.info("Für diese Website läuft bereits ein Job.")
            if st.button("Job kontrolliert abbrechen",key=f"cancel_{site_id}"):
                request_cancel(site_id)
                st.warning("Abbruch angefordert; die aktuell laufende Anfrage wird noch beendet.")
        elif job["state"] in ("failed","interrupted"):
            st.error(job["message"])
        else:
            st.success(job["message"])
    if st.button("Neuen Snapshot im Hintergrund starten",type="primary",
                 key=f"start_{site_id}",disabled=active or (snap_kind=="partial" and not runs(site_id))):
        try:
            started, job_id = launch(site_id,url,limit,snapshot_kind=snap_kind)
            st.success(f"Job #{job_id} gestartet." if started else f"Job #{job_id} läuft bereits.")
        except ValueError as exc:
            st.error(str(exc))
        st.rerun()

@st.fragment(run_every="2s")
def running_dashboard():
    from datetime import timezone
    found=0
    for entry in dashboard():
        job=latest(entry["id"])
        if not job or job["state"] not in ("queued","running"):
            continue
        found+=1
        info=json.loads(job["progress"] or "{}")
        start_time=datetime.fromisoformat(job["started_at"])
        elapsed=max(0,int((datetime.now(timezone.utc)-start_time).total_seconds()))
        st.write(f"**{entry['url']}** · Job #{job['id']} · gestartet {start_time.strftime('%d.%m. %H:%M')} UTC · Laufzeit {elapsed//60:02d}:{elapsed%60:02d}")
        if info.get("snapshot_kind")=="partial":
            percent=float(info.get("percent",0) or 0)
            st.progress(min(1,max(0,percent/100)),text=f"Partial: {percent:.1f}% · {info.get('changed',0)} zum Vorgänger · {info.get('changed_since_full',0)} zur Full-Baseline")
        else:
            st.caption(f"Full: {info.get('pages',0)} Seiten · {info.get('documents',0)} Dokumente · {info.get('discovered',0)} URLs gefunden")
            if info.get("limit_warnings"):
                st.warning("Schutzlimit erreicht: " + " · ".join(info["limit_warnings"]))
    if not found:
        st.caption("Keine aktiven Jobs.")

if current_page == "Dashboard":
    overview = dashboard()
    if overview:
        total_sites = len(overview)
        total_snapshots = sum(x["snapshots"] for x in overview)
        total_pages = sum(x["pages"] for x in overview)
        total_docs = sum(x["documents"] for x in overview)
        cols = st.columns(5)
        for col, label, value in zip(cols,
                                     ["Websites", "Snapshots", "Seiten (letzter Lauf)",
                                      "Dokumentlinks (letzter Lauf)", "Lokaler Speicher"],
                                     [total_sites, total_snapshots, total_pages, total_docs,
                                      f"{storage_bytes()/1048576:.2f} MB"]):
            col.metric(label, value)
        st.caption("Dokumente werden als Links gezählt, noch nicht heruntergeladen. "
                   "Speicher umfasst lokale Datenbankdateien; pro Website wird die Textmenge geschätzt.")
        st.subheader('Aktive Snapshot-Jobs')
        running_dashboard()
        st.subheader("Websites im Überblick")
        summary_rows = []
        for entry in overview:
            age = entry["oldest_age"]
            age_status = ("🔴 " if age is not None and age > 30 else "🟢 " if age is not None else "⚪ ")
            summary_rows.append({
                "Website": entry["url"],
                "Seiten": entry["pages"],
                "Dokumente": entry["documents"],
                "Snapshots": entry["snapshots"],
                "Ältester Snapshot": age_status + (f"{age} Tage" if age is not None else "Keiner"),
                "Letzter Snapshot (UTC)": entry["newest"][:16].replace("T"," ") if entry["newest"] else "—",
                "Offene URLs": entry["pending"],
                "Archivierter Text (MB)": round(entry["content_bytes"]/1048576,2)
            })
        st.dataframe(summary_rows, hide_index=True, width="stretch",
                     height=min(650, 38*(len(summary_rows)+1)+10),
                     column_config=streamlit_columns(summary_rows,links=("Website",)))
        st.info("Erfassungszahlen beziehen sich auf entdeckte URLs; eine garantiert "
                "vollständige Website-Erfassung ist technisch nicht nachweisbar.")
    else:
        st.info("Noch keine Websites registriert. Unter «Websites verwalten» hinzufügen.")

if current_page == "Websites verwalten":
    st.subheader("Websites verwalten")
    with st.expander("➕ Neue Website hinzufügen", expanded=False):
        with st.form("add_site", clear_on_submit=True):
            url = st.text_input("Neue Website oder Unterseite (https://...)",
                placeholder="https://www.zh.ch/de/bildung.html")
            st.caption("Ein Unterseiten-Link wird standardmässig nur mitsamt seinen "
                       "Unterseiten erfasst. Bei Websites mit .html-Endungen die "
                       "tatsächliche Startadresse verwenden; z. B. "
                       "https://www.zh.ch/de/bildung.html.")
            if st.form_submit_button("Website hinzufügen"):
                try:
                    add_site(url)
                    st.success("Website gespeichert.")
                    st.rerun()
                except (ValueError, OSError) as exc:
                    st.error(str(exc))
    if active_site_id is not None:
        entry = next((e for e in dashboard() if e["id"]==active_site_id), None)
        if entry:
            st.subheader("🌐 " + entry["url"])
            st.caption(f"Snapshots: {entry['snapshots']} · Seiten: {entry['pages']} · "
                       f"Dokumentlinks: {entry['documents']}")
            current = get_capture(entry["id"])
            setting_col, note_col = st.columns([3,2],vertical_alignment="top")
            with setting_col:
                mode = st.selectbox("Erfassungsmodus", options=list(MODES),
                    format_func=lambda m: MODES[m], index=list(MODES).index(current["mode"]),
                    key=f"mode_{entry['id']}")
            with note_col:
                if mode != STATIC:
                    st.info("Browsermodus benötigt Playwright und Chromium.")
            scope=st.selectbox("Erfassungsbereich",
                options=list(SCOPES),format_func=lambda value:SCOPES[value],
                index=list(SCOPES).index(current.get("crawl_scope","auto")),
                key=f"scope_{entry['id']}")
            resolved=effective_scope(entry["url"],scope)
            if resolved=="path":
                st.info("Unterbereich aktiv: Die Startseite und URLs unter "
                        f"**{logical_root(entry['url'])}/** werden erfasst. "
                        "PDF-/Word-Dateien, die von diesen Seiten direkt verlinkt "
                        "werden, können auch in einem gemeinsamen Dokumentverzeichnis liegen.")
            else:
                st.caption("Gesamte Domain: Interne Links dürfen in andere "
                           "Pfadbereiche der gleichen Domain führen.")
            with st.expander("Erweiterte Browser-Einstellungen"):
                selector = st.text_input("CSS-Selektor, auf den gewartet werden soll",
                    value=current["wait_selector"], key=f"selector_{entry['id']}")
                delay = st.number_input("Zusätzliche Wartezeit in Millisekunden", min_value=0,
                    max_value=30000, value=current["wait_ms"], step=500,
                    key=f"delay_{entry['id']}")
            if st.button("💾 Erfassungseinstellungen speichern", key=f"settings_{entry['id']}"):
                try:
                    set_settings(entry["id"],mode,selector,int(delay),scope=scope)
                    st.success("Einstellungen gespeichert.")
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))
            with st.expander("⚠️ Website entfernen", expanded=False):
                deletion = st.checkbox("Auch alle gespeicherten Snapshots dieser Website löschen",
                                       key=f"hist_{entry['id']}")
                confirm = st.checkbox("Entfernung bestätigen",key=f"confirm_{entry['id']}")
                if st.button("Website entfernen",key=f"remove_{entry['id']}",disabled=not confirm):
                    remove_site(entry["id"],delete_history=deletion)
                    st.session_state["active_site_id"]=None
                    st.success("Website entfernt.")
                    st.rerun()
    else:
        st.caption("Website links in der Seitenleiste auswählen oder neu hinzufügen.")
    st.caption("Ohne Löschen der Historie bleiben ältere Snapshots in der Datenbank erhalten, "
               "sind nach Entfernen der Website aber über die Oberfläche nicht mehr zugänglich.")

if current_page == "Snapshot starten":
    if not site_options or active_site_id is None:
        st.info("Bitte zuerst eine Website unter «Websites verwalten» hinzufügen.")
    else:
        site_id=active_site_id
        st.subheader("📸 Snapshot starten")
        st.caption(site_options[site_id])
        capture=get_capture(site_id)
        with st.container(border=True):
            a,b=st.columns([3,2],vertical_alignment="bottom")
            with a:
                snap_kind=st.radio("Snapshot-Art",["full","partial"],
                    format_func=lambda value:"Full / Baseline" if value=="full" else "Partial / Delta",
                    horizontal=True,key=f"snapshot_kind_{site_id}")
            with b:
                limit=st.number_input("Maximal besuchte URLs",10,100000,int(global_config["visit_limit"]),step=100,
                                      key=f"snapshot_limit_{site_id}")
            st.caption(f"Modus: {MODES[capture['mode']]} · "
                       f"Bereich: {SCOPES[capture.get('crawl_scope','auto')]} "
                       f"({effective_scope(site_options[site_id],capture.get('crawl_scope','auto'))}) · "
                       f"Discovery-Limit: {global_config['discovery_limit']:,} · "
                       f"Timeout: {global_config['page_timeout']} s · "
                       f"Parallele HTTP-Aufrufe: {global_config['http_workers']}. "
                       "Anpassbar unter «Einstellungen».")
            if int(limit)>20000 or int(global_config["http_workers"])>=8:
                st.warning("Belastungstest: Sehr viele URLs oder parallele Anfragen "
                    "können die Zielwebsite und deinen Rechner erheblich beanspruchen. "
                    "Zuerst die Erlaubnis und die Serverbelastung prüfen; "
                    "robots.txt wird beachtet. Laufende Jobs lassen sich "
                    "kontrolliert abbrechen.")
            job_controls(site_id,site_options[site_id],int(limit),snap_kind)

if current_page == "Snapshot-Verwaltung":
    if not site_options or active_site_id is None:
        st.info("Bitte zuerst eine Website hinzufügen.")
    else:
        site_id=active_site_id
        st.subheader("🗂️ Snapshot-Verwaltung")
        st.caption(site_options[site_id])
        history=runs(site_id)
        if not history:
            st.info("Noch keine Snapshots vorhanden. Unter «Snapshot starten» einen Lauf beginnen.")
        else:
            archive_rows=[]
            for row in history:
                job=snapshot_job(row[0])
                started=datetime.fromisoformat(job["started_at"]) if job else None
                ended=datetime.fromisoformat(job["ended_at"]) if job and job["ended_at"] else None
                seconds=max(0,int((ended-started).total_seconds())) if started and ended else None
                info=json.loads(job["progress"] or "{}") if job else {}
                archive_rows.append({
                    "ID":row[0],"Typ":kind(row[0])[0],
                    "Zeit (UTC)":row[1].replace("T"," ")[:19],
                    "Erfassung":"Abgeschlossen" if row[2]=="complete" else
                        "Unvollständig" if row[2]=="partial" else row[2],
                    "Laufzeit":f"{seconds//3600:02d}:{(seconds//60)%60:02d}:{seconds%60:02d}"
                               if seconds is not None else "—",
                    "URLs":info.get("discovered","—"),"Seiten":info.get("pages","—"),
                    "Dokumente":info.get("documents","—"),
                    "Warnungen/Fehler":len(json.loads(row[3] or "[]")),
                })
            st.dataframe(archive_rows,hide_index=True,width="stretch",
                column_config=streamlit_columns(archive_rows),height=min(440,36*(len(history)+1)+20))
            selected=st.selectbox("Snapshot-Details", [r[0] for r in history],
                                  key=f"snapshot_manage_{site_id}",
                                  format_func=lambda i:f"Snapshot #{i} · {kind(i)[0]}")
            record=next(r for r in history if r[0]==selected)
            job=snapshot_job(selected)
            progress=json.loads(job["progress"] or "{}") if job else {}
            issues=json.loads(record[3] or "[]")
            cols=st.columns(4)
            for col,label,key in zip(cols,
                ["URLs entdeckt","Besucht","Seiten","Dokumente"],
                ["discovered","visited","pages","documents"]):
                col.metric(label,progress.get(key,"—"))
            with st.expander("📋 Gesamte Job-Zusammenfassung",expanded=True):
                if job:
                    started=datetime.fromisoformat(job["started_at"])
                    ended=datetime.fromisoformat(job["ended_at"]) if job["ended_at"] else None
                    elapsed=(ended-started).total_seconds() if ended else None
                    st.caption("Job #"+str(job["id"])+" · "+job["state"]+
                        " · Start: "+started.strftime("%d.%m.%Y %H:%M:%S UTC")+
                        (" · Ende: "+ended.strftime("%d.%m.%Y %H:%M:%S UTC") if ended else ""))
                    if elapsed is not None:
                        elapsed=max(0,int(elapsed))
                        st.metric("Gesamtlaufzeit",
                            f"{elapsed//3600:02d}:{elapsed//60%60:02d}:{elapsed%60:02d}")
                else:
                    st.caption("Zu diesem älteren Snapshot sind keine Job-Zeitdaten vorhanden.")
                rows=[
                    {"Angabe":"Snapshot-Typ","Wert":kind(selected)[0]},
                    {"Angabe":"Erfassungsstatus","Wert":record[2]},
                ]+[{"Angabe":key,"Wert":str(value)} for key,value in progress.items()
                     if key not in ("errors","excluded_limits","limit_warnings","performance")]
                st.dataframe(rows,hide_index=True,width="stretch",height=360,
                    column_config=streamlit_columns(rows))
                if progress.get("limit_warnings"):
                    st.warning(" · ".join(progress["limit_warnings"]))
                if progress.get("excluded_limits"):
                    st.json(progress["excluded_limits"])
                st.download_button("Zusammenfassung als JSON herunterladen",
                    json.dumps({"snapshot_id":selected,"type":kind(selected)[0],
                                "status":record[2],"job":job,"errors":issues},
                               ensure_ascii=False,indent=2),
                    file_name=f"websnapshot_{selected}_summary.json",mime="application/json",
                    key=f"manage_export_{selected}")
            with st.expander(f"⚠️ Fehler und Warnungen ({len(issues)})",expanded=bool(issues)):
                if issues:
                    st.dataframe([{"Nr.":i,"Meldung":message}
                        for i,message in enumerate(issues,1)],hide_index=True,width="stretch",height=350,
                        column_config={"Nr.":st.column_config.Column(
                            width=column_width([{"Nr.":i,"Meldung":msg}
                                  for i,msg in enumerate(issues,1)],"Nr."))})
                    st.download_button("Fehlerprotokoll herunterladen",
                        json.dumps(issues,ensure_ascii=False,indent=2),
                        file_name=f"websnapshot_{selected}_errors.json",mime="application/json")
                else:
                    st.success("Keine Fehler oder Warnungen im Snapshot erfasst.")
            with st.expander("⏱️ Laufzeitstatistik und Seitentypen",expanded=True):
                measured=get_performance(selected)
                if not measured:
                    st.info("Für diesen älteren Snapshot sind keine Zeitmessungen gespeichert.")
                else:
                    names={"discovery_initial":"Initiale Discovery",
                        "robots_fetch":"robots.txt abrufen",
                        "sitemap_fetch":"Sitemaps abrufen",
                        "discovery_links":"Link-Discovery","page_fetch":"Seitenabrufe",
                        "snapshot_save":"Snapshot speichern",
                        "document_metadata":"Dokument-Metadaten",
                        "diagnostic_save":"Diagnose speichern"}
                    timing_rows=[
                        {"Phase":names.get(k,k),"Messungen":v["count"],
                         "Min. (ms)":v["min_ms"],"Ø (ms)":v["avg_ms"],
                         "Max. (ms)":v["max_ms"],"Summe (ms)":v["total_ms"],
                         "Langsamste URL":v.get("slowest_url","")}
                        for k,v in measured["timings"].items()]
                    st.dataframe(timing_rows,hide_index=True,width="stretch",
                        column_config=streamlit_columns(timing_rows))
                    m=st.columns(4)
                    m[0].metric("Statisch (HTTP)",measured["static_pages"])
                    m[1].metric("Browser: kaum dynamisch",measured["browser_static_pages"])
                    m[2].metric("Browser: JS ergänzt",measured["browser_dynamic_pages"])
                    m[3].metric("Timeouts",measured["timeouts"])
                    st.caption("Browser-Klassifikation ist eine Heuristik anhand des "
                        "Unterschieds zwischen Server-HTML und nach JavaScript erzeugtem DOM. "
                        "Nur im Browsermodus prüfbar; nicht eindeutig zu erkennen: "
                        +str(measured["browser_unknown_pages"]))
            with st.expander("🔬 Crawl-Diagnose"):
                diag=summary(selected)
                quality=diag["quality"]
                if quality:
                    st.write("**Qualität:** "+str(quality[10]))
                    if quality[9]:
                        st.warning("Erfassungsgrenze erreicht – Snapshot unvollständig.")
                    st.caption(f"Inhaltsduplikate: {quality[8]} · Fehler: {quality[7]}")
                st.write("URL-Quellen",diag["sources"])
                st.write("Bearbeitungsstatus",diag["statuses"])
                st.write("Ausschlussgründe",diag["reasons"])
                excluded_summary=excluded_link_stats(selected)
                st.markdown("**Links-pro-Seite: ausgelassene URLs und Quellseiten**")
                st.caption(f"{excluded_summary['excluded_links']:,} ausgelassene Links "
                           f"auf {excluded_summary['affected_pages']:,} Seiten."
                           .replace(",", "'"))
                if excluded_summary["excluded_links"]:
                    exclusion_query=st.text_input(
                        "Quellseiten und ausgeschlossene URLs durchsuchen",
                        placeholder="Pfad oder URL suchen …",
                        key=f"excluded_query_{selected}")
                    exclusion_total,excluded_rows=excluded_link_page(
                        selected,offset=0,limit=200,source_search=exclusion_query)
                    st.dataframe(excluded_rows,hide_index=True,width="stretch",
                        column_config={
                            "Quellseite":st.column_config.LinkColumn(
                                "Quellseite",width=340),
                            "Ausgeschlossene URL":st.column_config.LinkColumn(
                                "Nicht weiterverfolgte URL")})
                    st.caption(f"{len(excluded_rows)} von {exclusion_total} "
                               "Treffern sichtbar. CSV-Export in Blöcken "
                               "mit höchstens 10'000 Zeilen.")
                    max_chunk=max(1,(exclusion_total+9999)//10000)
                    chunk=st.number_input("Exportblock",
                        min_value=1,max_value=max_chunk,value=1,step=1,
                        key=f"excluded_chunk_{selected}")
                    if st.button("Ausschlussprotokoll als CSV vorbereiten",
                                 key=f"excluded_prep_{selected}"):
                        st.session_state[f"excluded_file_{selected}"] = (
                            excluded_link_csv_page(selected,
                                offset=(chunk-1)*10000,limit=10000,
                                source_search=exclusion_query))
                    prepared=st.session_state.get(f"excluded_file_{selected}")
                    if prepared is not None:
                        st.download_button("Ausgeschlossene URLs als CSV herunterladen",
                            data=prepared,mime="text/csv",
                            file_name=f"websnapshot_{selected}_link_ausschluesse.csv",
                            key=f"excluded_export_{selected}")
                a,b=st.columns(2)
                path_rows=[{"Pfad":path,"Varianten":count}
                           for path,count in diag["paths"]]
                parameter_rows=[{"Parameter":name,"Vorkommen":count}
                                for name,count in diag["parameters"]]
                a.dataframe(path_rows,hide_index=True,width="stretch",
                            column_config=streamlit_columns(path_rows))
                b.dataframe(parameter_rows,hide_index=True,width="stretch",
                            column_config=streamlit_columns(parameter_rows))
            with st.expander("🗑️ Snapshot löschen"):
                st.warning("Die Löschung ist endgültig. Full-Snapshots mit abhängigen "
                           "Delta-Snapshots können nicht gelöscht werden.")
                confirm=st.checkbox("Löschung bestätigen",key=f"confirm_delete_{selected}")
                if st.button("Snapshot endgültig löschen",
                             disabled=not confirm or running()>0,key=f"delete_{selected}"):
                    try:
                        remove_snapshot(site_id,selected)
                        st.success("Snapshot entfernt.")
                        st.rerun()
                    except ValueError as exc:
                        st.error(str(exc))

if current_page == "Änderungsvergleich":
    if not site_options or active_site_id is None:
        st.info("Bitte zuerst eine Website hinzufügen.")
    else:
        site_id=active_site_id
        st.subheader("🔍 Änderungen vergleichen")
        st.caption(site_options[site_id])
        history=runs(site_id)
        if len(history)<2:
            st.info("Für einen Vergleich müssen mindestens zwei Snapshots gespeichert sein.")
        else:
            ids=[r[0] for r in history]
            before_col,after_col=st.columns(2)
            old_id=before_col.selectbox("Vorher",ids,index=1,key=f"before_{site_id}")
            new_id=after_col.selectbox("Nachher",ids,index=0,key=f"after_{site_id}")
            if old_id==new_id:
                st.info("Bitte zwei unterschiedliche Snapshots auswählen.")
            else:
                changes=compare(old_id,new_id)
                st.metric("Unterschiedliche Seiten",len(changes))
                if not changes:
                    st.success("Zwischen diesen Snapshots sind keine Textänderungen erkennbar.")
                else:
                    kind_filter=st.radio("Änderungen anzeigen",
                        ["Alle","Geändert","Neu","Fehlend"],horizontal=True,
                        key=f"change_filter_{site_id}")
                    map_filter={"Geändert":"changed","Neu":"added","Fehlend":"missing"}
                    display=[item for item in changes if kind_filter=="Alle" or
                             item["kind"]==map_filter.get(kind_filter)]
                    st.caption(f"{len(display)} von {len(changes)} Ergebnissen")
                    if display:
                        selected=st.selectbox("Seite auswählen",range(len(display)),
                            format_func=lambda i:f"{display[i]['kind']} · {display[i]['title']} · "
                                                  f"{display[i]['url']}",
                            key=f"diff_page_{site_id}_{old_id}_{new_id}_{kind_filter}")
                        change=display[selected]
                        st.caption("HTML-Textvergleich direkt im Browser. "
                                   "Die ursprüngliche Seitengestaltung wird nicht gespeichert.")
                        st.link_button("🌐 Aktuelle Originalseite öffnen",change["url"])
                        from websnapshot.ui_diff import comparison_html
                        old_pages=effective_pages(old_id)
                        new_pages=effective_pages(new_id)
                        url=change["url"]
                        before=old_pages[url][1] if url in old_pages else ""
                        after=new_pages[url][1] if url in new_pages else ""
                        st.components.v1.html(
                            comparison_html(before,after,change["title"]),
                            height=620,scrolling=True)
                        with st.expander("Technische Textänderungen"):
                            st.code(change["diff"] or "Keine Zeilendifferenz vorhanden",
                                    language="diff")
                with st.expander("⬇️ Optional: HTML-Änderungsbericht herunterladen"):
                    st.download_button("HTML-Bericht herunterladen",
                        report(changes,old_id,new_id),
                        file_name=f"websnapshot_{old_id}_{new_id}.html",
                        mime="text/html",key=f"compare_export_{old_id}_{new_id}")
                st.caption("Hinweis: Eine im Snapshot fehlende Seite gilt "
                           "nicht automatisch als gelöscht.")

if current_page == "Dokumente":
    if not site_options or active_site_id is None:
        st.info("Bitte zuerst eine Website hinzufügen.")
    else:
        site_id=active_site_id
        st.subheader("📄 Dokumente herunterladen")
        st.caption(site_options[site_id])
        history=runs(site_id)
        if not history:
            st.info("Noch keine Snapshots oder Dokumente erfasst.")
        else:
            doc_run = st.selectbox("Dokumentinventar", [r[0] for r in history],
                                   key=f"document_run_{site_id}")
            docs = list_documents(doc_run)
            st.caption("PDF-, Word-, Excel-, TXT- und CSV-Dateien werden ausschliesslich nach Auswahl "
                       "heruntergeladen. Suche und Auswahl gelten nur für diesen Snapshot.")
            with st.expander("🏷️ Dokument-Renamer",expanded=True):
                saved_profile=get_profile(site_id)
                renamer_mode=st.radio("Dateiname",
                    [RENAMED,ORIGINAL],
                    format_func=lambda mode: "YYYY_MM_DD_HERKUNFT_Dokumentenname" if mode==RENAMED
                        else "Originalname (ohne Präfix)",
                    index=0 if saved_profile["mode"]==RENAMED else 1,
                    horizontal=True,key=f"rename_mode_{site_id}")
                a,b=st.columns(2)
                with a:
                    renamer_code=st.text_input("Herkunftskürzel",
                        value=saved_profile["code"],max_chars=16,
                        placeholder="DSB / SEKB",key=f"rename_code_{site_id}",
                        disabled=renamer_mode==ORIGINAL)
                with b:
                    renamer_case=st.selectbox("Schreibweise",
                        list(CASE_MODES),format_func=lambda val:CASE_MODES[val],
                        index=list(CASE_MODES).index(saved_profile["case"]),
                        key=f"rename_case_{site_id}",disabled=renamer_mode==ORIGINAL)
                if st.button("Renamer-Einstellungen speichern",key=f"save_rename_{site_id}"):
                    try:
                        set_profile(site_id,mode=renamer_mode,code=renamer_code,
                                    case=renamer_case)
                        st.success("Renamer-Profil gespeichert.")
                        st.rerun()
                    except ValueError as exc:
                        st.error(str(exc))
                st.caption("Datum: zuerst verfügbare PDF-/Office-Metadaten, dann HTTP Last-Modified, "
                           "sonst Download-Datum (Ersatzwert). "
                           "Dateinamenkollisionen werden mit _2, _3 usw. gelöst; "
                           "SHA-256 bleibt ausschliesslich intern.")
                if docs:
                    first=docs[0]
                    stem=filename_from_headers(first["url"])
                    extension="."+stem.rsplit(".",1)[-1].lower() if "." in stem else ".pdf"
                    if extension not in (".pdf",".doc",".docx",".xlsx",".xls",".txt",".csv"):
                        extension=".pdf"
                    preview_date,origin=choose_date(
                        ("Dokumentintern geändert",first.get("modified")),
                        ("Dokumentintern erstellt",first.get("created")),
                        ("HTTP Last-Modified",first.get("last_modified")))
                    try:
                        st.code(build_filename(stem,extension,
                            mode=renamer_mode,code=renamer_code,
                            case=renamer_case,date=preview_date),language=None)
                        st.caption("Beispiel anhand des ersten Dokuments; endgültiger "
                                   "Name kann aufgrund von Dateimetadaten variieren.")
                    except ValueError:
                        st.caption("Bitte ein gültiges Herkunftskürzel eingeben.")
            if not docs:
                st.info("Für diesen Snapshot ist keine Dokumentliste vorhanden.")
            else:
                prefix = f"doc_{site_id}_{doc_run}"
                selection_key = f"{prefix}_selected_urls"
                revision_key = f"{prefix}_editor_revision"
                previous_filter_key = f"{prefix}_previous_filter"
                selected_urls = set(st.session_state.get(selection_key, []))
                all_urls = [d["url"] for d in docs]
                valid_urls = set(all_urls)
                selected_urls &= valid_urls
                search = st.text_input("Dokumente suchen",
                    placeholder="Dateiname, Titel, Autor, Fundstelle oder Änderungsstatus suchen …",
                    key=f"{prefix}_search",help="Gross-/Kleinschreibung spielt keine Rolle.")
                if st.session_state.get(previous_filter_key) != search:
                    st.session_state[previous_filter_key] = search
                    st.session_state[revision_key] = st.session_state.get(revision_key,0)+1
                filtered_docs = filter_documents(docs,search)
                visible_urls = [d["url"] for d in filtered_docs]
                st.caption(f"**{len(filtered_docs)} von {len(docs)}** Dokumenten sichtbar · "
                           f"**{len(selected_urls)}** insgesamt ausgewählt")
                button_cols = st.columns(4)
                actions = [
                    ("☑️ Alle auswählen","all_select"),
                    ("☐ Alle abwählen","all_clear"),
                    ("☑️ Gefilterte auswählen","filtered_select"),
                    ("☐ Gefilterte abwählen","filtered_clear")]
                for col,(caption,action) in zip(button_cols,actions):
                    with col:
                        if st.button(caption,key=f"{prefix}_{action}",
                                     use_container_width=True,
                                     disabled=not docs or (
                                         action.startswith("filtered") and not filtered_docs)):
                            selected_urls = bulk_selection(
                                selected_urls,all_urls,visible_urls,action)
                            st.session_state[revision_key] = (
                                st.session_state.get(revision_key,0)+1)
                st.caption("Auswahl direkt in der ersten Tabellenspalte ändern. "
                           "«Gefilterte abwählen» lässt ausgeblendete Dokumente ausgewählt.")
                if filtered_docs:
                    editor_rows = [
                        {"Auswahl":d["url"] in selected_urls,
                         "Dokument":d["url"],"Titel":d.get("title") or "",
                         "Autor":d.get("author") or "",
                         "Erstellt":d.get("created") or "",
                         "Geändert":d.get("modified") or d.get("last_modified") or "",
                         "Status":d.get("property_status") or d["status"],
                         "Fundstellen":d.get("references",0),
                         "Grösse (HTTP)":d["length"] or "Unbekannt",
                         "Gespeichert":bool(d["downloaded"])}
                        for d in filtered_docs]
                    revision = st.session_state.get(revision_key,0)
                    edited = st.data_editor(
                        editor_rows,key=f"{prefix}_editor_{revision}",
                        hide_index=True,width="stretch",height=490,
                        num_rows="fixed",row_height=33,
                        disabled=[key for key in editor_rows[0] if key!="Auswahl"],
                        column_config={
                            "Auswahl":st.column_config.CheckboxColumn(
                                "Auswahl",width=100,required=True),
                            "Dokument":st.column_config.LinkColumn(
                                "Dokument / URL",width=column_width(editor_rows,"Dokument")),
                            "Titel":st.column_config.TextColumn(
                                "Dokumenttitel",width=column_width(editor_rows,"Titel")),
                            "Autor":st.column_config.TextColumn(
                                "Autor",width=column_width(editor_rows,"Autor")),
                            "Erstellt":st.column_config.TextColumn(
                                "Erstellt",width=column_width(editor_rows,"Erstellt")),
                            "Geändert":st.column_config.TextColumn(
                                "Geändert",width=column_width(editor_rows,"Geändert")),
                            "Status":st.column_config.TextColumn(
                                "Änderungsstatus",width=column_width(editor_rows,"Status")),
                            "Fundstellen":st.column_config.NumberColumn(
                                "Fundstellen",width=110),
                            "Grösse (HTTP)":st.column_config.TextColumn(
                                "Grösse",width=120),
                            "Gespeichert":st.column_config.CheckboxColumn("Heruntergeladen")})
                    visible_selected={row["Dokument"] for row in edited if row["Auswahl"]}
                    selected_urls=merge_visible(
                        selected_urls,all_urls,visible_urls,visible_selected)
                else:
                    st.info("Keine Dokumente passen zum Suchbegriff. "
                            "Du kannst den Filter löschen oder neu suchen.")
                with st.expander("🔎 Dokumenteigenschaften und Fundstellen",expanded=False):
                    if filtered_docs:
                        details_url=st.selectbox(
                            "Dokument auswählen",
                            [d["url"] for d in filtered_docs[:500]],
                            key=f"{prefix}_details")
                        details=next(d for d in docs if d["url"]==details_url)
                        ref_rows=list_references(doc_run,details_url)
                        st.caption(f"**{len(ref_rows)} Fundstellen** · "
                                   f"Dateimetadaten: {details.get('property_status') or 'Noch nicht geprüft'}")
                        if ref_rows:
                            st.dataframe([{"Fundstelle":r["url"],"Quelle":r["type"]}
                                          for r in ref_rows],
                                         width="stretch",hide_index=True,
                                         column_config={
                                            "Fundstelle":st.column_config.LinkColumn(
                                                "Gefunden auf",width="large")})
                        else:
                            st.caption("Keine Quellseiten gespeichert – bei älteren "
                                       "Snapshots werden Fundstellen nicht nachträglich ermittelt.")
                        http_rows=[
                            {"Eigenschaft":"HTTP ETag","Wert":details.get("etag") or "–"},
                            {"Eigenschaft":"HTTP Last-Modified",
                             "Wert":details.get("last_modified") or "–"},
                            {"Eigenschaft":"HTTP Content-Length",
                             "Wert":details.get("length") or "–"},
                            {"Eigenschaft":"SHA-256 (intern)",
                             "Wert":details.get("sha256") or "Noch nicht geprüft"},
                        ]
                        st.dataframe(http_rows+display_properties(details.get("properties") or {}),
                            hide_index=True,width="stretch")
                        if details.get("property_error"):
                            st.warning(details["property_error"])
                        if st.button("Eigenschaften dieses Dokuments prüfen",
                                     key=f"{prefix}_probe_one"):
                            with st.spinner("Dokument temporär abrufen und Metadaten lesen …"):
                                result=probe_selected(doc_run,[details_url])
                            if result[0].get("error"):
                                st.error(result[0]["error"])
                            else:
                                st.success(f"Eigenschaften gelesen · {result[0]['status']}.")
                            st.rerun()
                    else:
                        st.caption("Keine Dokumente für diesen Filter.")
                st.caption("Vor dem eigentlichen Download zeigt die Inventarisierung "
                           "HTTP-Metadaten. Für eingebettete PDF-/Office-Eigenschaften "
                           "und SHA-256 wird die Datei bei einer ausdrücklichen Prüfung "
                           "temporär übertragen (maximal 20 MB) und danach gelöscht. "
                           "TXT/CSV enthalten normalerweise keine eingebetteten Office-Tags.")
                if selected_urls:
                    if st.button("🔬 Eigenschaften und SHA-256 der Auswahl prüfen",
                                 key=f"{prefix}_probe_selected",
                                 disabled=len(selected_urls)>20):
                        with st.spinner(f"{len(selected_urls)} Dokumente temporär prüfen …"):
                            inspected=probe_selected(doc_run,sorted(selected_urls))
                        failures=[entry for entry in inspected if entry.get("error")]
                        if failures:
                            st.warning(f"{len(failures)} von {len(inspected)} Dokumenten "
                                       "konnten nicht geprüft werden.")
                            for entry in failures[:10]:
                                st.caption(f"{entry['url']}: {entry['error']}")
                        else:
                            st.success(f"{len(inspected)} Dokumente erfolgreich geprüft.")
                        st.rerun()
                    if len(selected_urls)>20:
                        st.caption("Für eine Metadatenprüfung höchstens 20 Dokumente "
                                   "gleichzeitig auswählen. Der normale Download "
                                   "bleibt davon unabhängig.")
                st.session_state[selection_key]=sorted(selected_urls)
                st.caption(f"**{len(selected_urls)} Dokumente für den Download vorgemerkt** "
                           "– auch ausserhalb des aktuellen Suchfilters.")
                st.caption("Globales Download-Verzeichnis: "
                           + str(global_config["download_directory"]))
                layout = st.radio("Speicherstruktur",
                    ["Website-Ordnerstruktur","Flacher Ordner"],
                    index=1 if global_config["flat_downloads"] else 0,
                    horizontal=True,key=f"{prefix}_layout")
                if st.button(f"⬇️ {len(selected_urls)} ausgewählte Dokumente herunterladen",
                             disabled=not selected_urls,key=f"{prefix}_download",
                             type="primary"):
                    try:
                        set_profile(site_id,mode=renamer_mode,code=renamer_code,
                                    case=renamer_case)
                        with st.spinner(f"{len(selected_urls)} Dokumente herunterladen …"):
                            outcomes=download_selected(
                                doc_run,sorted(selected_urls),
                                flat=layout=="Flacher Ordner",
                                profile={"mode":renamer_mode,"code":renamer_code,
                                         "case":renamer_case},
                                destination_root=Path(global_config["download_directory"]))
                        count_ok=sum("error" not in item for item in outcomes)
                        st.success(f"{count_ok} von {len(outcomes)} Dokumenten gespeichert.")
                        for item in outcomes:
                            if "error" in item:
                                st.error(f"{item['url']}: {item['error']}")
                            else:
                                st.caption(f"✔ {item['path']} · Datum: {item['date_source']} "
                                           f"({item['date']}) · SHA-256 intern gespeichert")
                        st.caption("Download-Verzeichnis: "
                                   +str(global_config["download_directory"]))
                    except ValueError as exc:
                        st.error(str(exc))

if current_page == "Sitemap":
    st.subheader("🗺️ Sitemap / erfasste Seiten")
    if active_site_id not in site_options:
        st.info("Bitte zuerst eine Website hinzufügen.")
    else:
        site_id=active_site_id
        st.caption(f"🌐 {site_options[site_id]} · Website wechseln: linke Seitenleiste")
        history=runs(site_id)
        if not history:
            st.info("Für diese Website existiert noch kein Snapshot.")
        else:
            selected_run=st.selectbox("Snapshot",
                [r[0] for r in history],key=f"sitemap_run_{site_id}",
                format_func=lambda i:f"Snapshot #{i}")
            # Read URLs/titles/lengths from SQLite, not potentially huge HTML bodies.
            table=effective_page_metadata(selected_run)
            tools_left,tools_right=st.columns([3,2],vertical_alignment="bottom")
            with tools_left:
                view_mode=st.radio("Darstellung",["Verzeichnisbaum","Flache Tabelle"],
                    key=f"sitemap_mode_{site_id}",horizontal=True)
            with tools_right:
                table_height=st.select_slider("Tabellenhöhe",
                    options=[350,550,800,1100,1500],
                    value=int(global_config["sitemap_height"]),
                    format_func=lambda x:f"{x} px",key=f"sitemap_height_{site_id}")
            search=st.text_input("Sitemap durchsuchen",
                placeholder="Verzeichnis, Pfad, Titel oder URL suchen …",
                key=f"sitemap_search_{site_id}")
            filtered=filtered_page_rows(table,search)
            st.caption(f"**{len(filtered):,} von {len(table):,}** archivierten Seiten "
                       "· inklusive geerbter Full-Baseline".replace(",", "'"))
            if view_mode=="Flache Tabelle":
                st.dataframe(filtered,hide_index=True,width="stretch",
                    height=table_height,row_height=32,
                    column_order=["Pfad","Titel","Zeichen","Öffnen","URL"],
                    column_config={
                        "Pfad":st.column_config.TextColumn("Pfad",width=column_width(filtered,"Pfad")),
                        "Titel":st.column_config.TextColumn("Seitentitel",
                            width=column_width(filtered,"Titel")),
                        "Zeichen":st.column_config.NumberColumn("Zeichen",format="%d",
                            width=column_width(filtered,"Zeichen")),
                        "Öffnen":st.column_config.LinkColumn("Original",
                            display_text="Öffnen ↗",width=110),
                        "URL":st.column_config.TextColumn("URL")})
                st.caption("Die flache Ansicht lässt sich durch Klick auf einen "
                           "Spaltenkopf beliebig sortieren.")
            else:
                tree=tree_from_pages(filtered)
                expanded_key=f"sitemap_expanded_{site_id}_{selected_run}"
                version_key=f"sitemap_tree_version_{site_id}_{selected_run}"
                expanded=set(st.session_state.get(expanded_key,[]))
                if search.strip():
                    expanded=all_parent_ids(tree)
                    st.caption("Beim Suchen werden die Verzeichnisse mit Treffern "
                               "automatisch aufgeklappt.")
                tree_a,tree_b=st.columns(2)
                with tree_a:
                    if st.button("📂 Erste Ebene aufklappen",
                                 key=f"tree_first_{site_id}_{selected_run}",
                                 use_container_width=True,disabled=bool(search.strip())):
                        expanded|={node["id"] for node in tree["children"].values()
                                   if node["children"]}
                        st.session_state[expanded_key]=sorted(expanded)
                        st.session_state[version_key]=st.session_state.get(version_key,0)+1
                        st.rerun()
                with tree_b:
                    if st.button("📁 Alle Verzeichnisse schliessen",
                                 key=f"tree_close_{site_id}_{selected_run}",
                                 use_container_width=True,disabled=bool(search.strip())):
                        st.session_state[expanded_key]=[]
                        st.session_state[version_key]=st.session_state.get(version_key,0)+1
                        st.rerun()
                rows,node_ids,truncated=visible_tree_rows(tree,expanded,limit=2500)
                if rows:
                    revision=st.session_state.get(version_key,0)
                    filter_token=sha1(search.encode("utf-8")).hexdigest()[:12]
                    edited=st.data_editor(rows,
                        key=f"sitemap_tree_{site_id}_{selected_run}_{filter_token}_{revision}",
                        hide_index=True,width="stretch",height=table_height,
                        num_rows="fixed",row_height=34,
                        disabled=["Ebene / Pfad","Seiten","Titel",
                                  "Zeichen","Öffnen","URL"]+
                                 (["Aufklappen"] if search.strip() else []),
                        column_order=["Aufklappen","Ebene / Pfad","Seiten",
                                      "Titel","Zeichen","Öffnen","URL"],
                        column_config={
                            "Aufklappen":st.column_config.CheckboxColumn(
                                "Aufklappen",width=100,required=True),
                            "Ebene / Pfad":st.column_config.TextColumn(
                                "Verzeichnis / Pfad",
                                width=column_width(rows,"Ebene / Pfad",cap=410)),
                            "Seiten":st.column_config.NumberColumn("Seiten",
                                width=column_width(rows,"Seiten")),
                            "Titel":st.column_config.TextColumn("Seitentitel",
                                width=column_width(rows,"Titel",cap=370)),
                            "Zeichen":st.column_config.NumberColumn("Zeichen",
                                width=column_width(rows,"Zeichen")),
                            "Öffnen":st.column_config.LinkColumn(
                                "Original",display_text="Öffnen ↗",width=110),
                            "URL":st.column_config.TextColumn("URL")})
                    if not search.strip():
                        changed=False
                        for i,row in enumerate(edited):
                            if row["Aufklappen"]==rows[i]["Aufklappen"]:
                                continue
                            node_id=node_ids[i]
                            if row["Aufklappen"]:
                                expanded.add(node_id)
                            else:
                                expanded.discard(node_id)
                            changed=True
                        if changed:
                            st.session_state[expanded_key]=sorted(expanded)
                            st.session_state[version_key]=revision+1
                            st.rerun()
                else:
                    st.info("Keine Seiten entsprechen dem Suchbegriff.")
                if truncated:
                    st.warning("Die Baumtabelle zeigt höchstens 2'500 geöffnete "
                               "Einträge gleichzeitig. Weitere Verzeichnisse schliessen "
                               "oder die Suche verwenden.")
                st.caption("Zum Öffnen eines Ordners das Kontrollkästchen in der "
                           "ersten Spalte aktivieren. Eine Seite kann gleichzeitig "
                           "ein Ordner mit Unterseiten sein.")
            with st.expander("⬇️ Sitemap als Excel oder CSV exportieren"):
                st.caption("Exportiert **alle** Seiten des gewählten Snapshots, "
                           "unabhängig vom aktuellen Suchfilter. "
                           "Bei grossen Snapshots kann die Erstellung einige Sekunden dauern.")
                export_key=f"sitemap_export_{site_id}_{selected_run}"
                if st.button("Exporte vorbereiten",
                             key=f"prepare_export_{site_id}_{selected_run}"):
                    with st.spinner(f"{len(table):,} Seiten exportieren …"):
                        st.session_state[export_key]={
                            "csv":export_csv(table),
                            "xlsx":export_xlsx(table)}
                if export_key in st.session_state:
                    files=st.session_state[export_key]
                    c1,c2=st.columns(2)
                    with c1:
                        st.download_button("CSV herunterladen",
                            files["csv"],file_name=f"websnapshot_sitemap_{selected_run}.csv",
                            mime="text/csv",key=f"sitemap_csv_{selected_run}")
                    with c2:
                        st.download_button("Excel (.xlsx) herunterladen",
                            files["xlsx"],
                            file_name=f"websnapshot_sitemap_{selected_run}.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            key=f"sitemap_xlsx_{selected_run}")


if current_page == "Job-Protokolle":
    if not site_options or active_site_id is None:
        st.info("Bitte zuerst eine Website hinzufügen.")
    else:
        site_id=active_site_id
        st.subheader("📋 Job-Protokolle")
        st.caption(site_options[site_id])
        job=latest(site_id)
        if job:
            st.write(f"**Letzter Job #{job['id']} · {job['state']}**")
            last_activity=job.get("last_activity_at") or job.get("last_progress_at")
            if last_activity:
                st.caption("Letzte Aktivität (UTC): "+last_activity)
                if job["state"]=="running":
                    from datetime import timezone
                    idle=int((datetime.now(timezone.utc)-
                        datetime.fromisoformat(last_activity)).total_seconds())
                    if idle>60:
                        st.warning(f"Seit {idle} Sekunden keine neue Fortschrittsmeldung.")
            from websnapshot.job_logging import read as read_job_log, log_path
            st.code(read_job_log(job["id"]),language="text")
            if log_path(job["id"]).is_file():
                st.download_button("Logdatei herunterladen",
                    data=log_path(job["id"]).read_bytes(),
                    file_name=f"job_{job['id']}.log",mime="text/plain")
        else:
            st.info("Noch kein Job vorhanden.")
        history=runs(site_id)
        history_jobs=[snapshot_job(r[0]) for r in history]
        history_jobs=[j for j in history_jobs if j]
        if history_jobs:
            with st.expander("Ältere Job-Protokolle"):
                from websnapshot.job_logging import read as read_job_log, log_path
                choices={j["id"]:j for j in history_jobs}
                chosen=st.selectbox("Job auswählen",list(choices),
                    format_func=lambda j:f"Job #{j}",key=f"logs_history_{site_id}")
                st.code(read_job_log(chosen),language="text")
                if log_path(chosen).is_file():
                    st.download_button("Historische Logdatei herunterladen",
                        data=log_path(chosen).read_bytes(),
                        file_name=f"job_{chosen}.log",mime="text/plain",
                        key=f"log_dl_{chosen}")

if current_page == "Einstellungen":
    st.subheader("⚙️ Allgemeine Einstellungen")
    st.caption("Gelten für alle Websites und bleiben in der lokalen Datenbank erhalten. "
               "Spezifische Einstellungen wie Browsermodus und Herkunftskürzel "
               "bleiben bei der einzelnen Website.")
    with st.form("global_preferences"):
        st.markdown("**Dokumentdownloads**")
        download_dir=st.text_input("Download-Verzeichnis",
            value=str(global_config["download_directory"]),
            placeholder=r"D:\\Dokumente\\WebSnapshot")
        default_flat=st.checkbox("Standardmässig alle Dateien im Website-Ordner speichern "
                                 "(ohne Unterordner)",
            value=bool(global_config["flat_downloads"]))
        st.caption("Ein absoluter Pfad auf einem lokalen Laufwerk oder Netzlaufwerk ist "
                   "erlaubt. Das Zielverzeichnis wird beim Speichern geprüft. "
                   "Bereits heruntergeladene Dateien werden nicht verschoben.")
        st.divider()
        st.markdown("**Standardwerte für neue Erfassungen und Ansichten**")
        default_limit=st.number_input("Standard-Besuchslimit",
            min_value=10,max_value=100000,
            value=int(global_config["visit_limit"]),step=100)
        st.markdown("**Crawl-Grenzen und Geschwindigkeit**")
        discovery_limit=st.number_input("Discovery-Limit – maximal entdeckte URLs",
            min_value=1000,max_value=1_000_000,
            value=int(global_config.get("discovery_limit",200000)),step=10000)
        page_timeout=st.number_input("Antwort-Timeout pro Seite (Sekunden)",
            min_value=1.0,max_value=60.0,
            value=float(global_config.get("page_timeout",3.0)),
            step=0.5)
        links_per_page=st.number_input("Links-pro-Seite-Limit",
            min_value=1,max_value=10000,
            value=int(global_config.get("links_per_page",1000)),step=100,
            help="Maximal berücksichtigte Links pro HTML-Seite. Jede wegen des "
                 "Limits ausgeschlossene URL wird mit ihrer Quellseite protokolliert.")
        st.caption("Standard: 1'000. Die betroffenen Seiten und URLs findest du "
                   "nach dem Lauf unter «Snapshot-Verwaltung → Crawl-Diagnose».")

        http_workers=st.slider("Parallele statische HTTP-Aufrufe",
            min_value=1,max_value=10,
            value=int(global_config.get("http_workers",3)))
        st.caption("Der HTTP-Timeout begrenzt Verbindungsaufbau und Phasen ohne "
                   "empfangene Daten, nicht zwingend die Gesamtdauer einer Antwort. "
                   "Browserseiten werden weiterhin nacheinander gerendert.")
        default_sitemap=st.select_slider("Standardhöhe der Sitemap-Tabelle",
            options=list(VALID_HEIGHTS),value=int(global_config["sitemap_height"]),
            format_func=lambda x:f"{x} px")
        save_clicked=st.form_submit_button("💾 Einstellungen speichern",
                                           type="primary")
    if save_clicked:
        try:
            save_global(download_directory=download_dir,
                        flat_downloads=default_flat,
                        visit_limit=int(default_limit),
                        sitemap_height=int(default_sitemap),
                        discovery_limit=int(discovery_limit),
                        page_timeout=float(page_timeout),
                        http_workers=int(http_workers),
                        links_per_page=int(links_per_page))
            st.success("Globale Einstellungen gespeichert.")
            st.rerun()
        except ValueError as exc:
            st.error(str(exc))


if current_page == "Updates":
    with st.expander("Unterbrochene Job-Sperren freigeben"):
        st.caption("Nur nach einem Neustart ausführen, wenn definitiv kein Snapshot mehr läuft.")
        if st.button("Sperren manuell freigeben"):
            st.success(f"{recover_interrupted()} Jobs als unterbrochen markiert.")
    st.subheader("Anwendung aktualisieren")
    st.write("Übernimmt neue Änderungen aus dem konfigurierten GitHub-Repository "
             "und installiert Python-Abhängigkeiten. Keine Updates während eines Crawls starten.")
    st.warning("Nur für die lokale Einzelplatzinstallation. Git muss verfügbar sein; "
               "lokale Codeänderungen können das Update verhindern. "
               "Vorher wichtige Daten aus .data sichern.")
    if running():
        st.warning("Updates sind gesperrt, solange Snapshot-Jobs aktiv sind.")
    confirm_update = st.checkbox("Ich möchte den aktuellen GitHub-Stand installieren.")
    if st.button("Update installieren und Anwendung neu starten",disabled=not confirm_update or running()>0):
        try:
            status = subprocess.run(["git", "-C", str(ROOT), "status", "--porcelain"],
                                    text=True,capture_output=True,timeout=15,check=True)
            if status.stdout.strip():
                st.error("Lokale Änderungen vorhanden. Bitte vor dem Update sichern/committen.")
            else:
                pull = subprocess.run(["git","-C",str(ROOT),"pull","--ff-only"],
                                      text=True,capture_output=True,timeout=120,check=True)
                install = subprocess.run([sys.executable,"-m","pip","install","-e",str(ROOT)],
                                         text=True,capture_output=True,timeout=240,check=True)
                st.success("Update abgeschlossen. Anwendung wird neu geladen.")
                st.code(pull.stdout[-1500:] + "\n" + install.stdout[-1500:])
                st.rerun()
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError) as exc:
            st.error(f"Update fehlgeschlagen: {exc}")
            if isinstance(exc, subprocess.CalledProcessError):
                st.code((exc.stderr or exc.stdout or "")[-3000:])
