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
from websnapshot.jobs import launch, latest, running, recover_interrupted, request_cancel, snapshot_job
from websnapshot.diagnostics import summary
from websnapshot.settings import MODES, STATIC, get as get_capture, set_settings
from websnapshot.versions import kind, effective_pages, remove_snapshot
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[2]
st.set_page_config(page_title="WebSnapshot", page_icon="📸", layout="wide",
                   initial_sidebar_state="collapsed")
st.markdown("""
<style>
.block-container {max-width: 100% !important; padding-top: 1rem !important;
                  padding-bottom: 1.2rem !important; padding-left: 1.5rem !important;
                  padding-right: 1.5rem !important;}
h1 {font-size: 1.7rem !important; margin-bottom: .1rem !important;}
h2, h3 {margin-top: .65rem !important; margin-bottom: .35rem !important;}
div[data-testid="stMetric"] {padding: .25rem .5rem;}
div[data-testid="stMetricValue"] {font-size: 1.55rem;}
div[data-testid="stVerticalBlock"] {gap: .55rem;}
div[data-testid="stTabs"] button {padding-top: .45rem; padding-bottom: .45rem;}
</style>
""", unsafe_allow_html=True)
st.title("WebSnapshot")
st.caption("Lokale Website-Inventarisierung · Version 0.6.3")

tab_overview, tab_sites, tab_snapshots, tab_map, tab_system = st.tabs(
    ["Dashboard", "Websites verwalten", "Snapshots & Vergleich", "Sitemap", "Updates"])


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
            discovery_limit=int(info.get("discovery_limit",10000) or 10000)
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

with tab_overview:
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
                     column_config={"Website":st.column_config.LinkColumn("Website")})
        st.info("Erfassungszahlen beziehen sich auf entdeckte URLs; eine garantiert "
                "vollständige Website-Erfassung ist technisch nicht nachweisbar.")
    else:
        st.info("Noch keine Websites registriert. Unter «Websites verwalten» hinzufügen.")

with tab_sites:
    with st.form("add_site", clear_on_submit=True):
        url = st.text_input("Neue Website (https://...)")
        if st.form_submit_button("Website hinzufügen"):
            try:
                add_site(url)
                st.success("Website gespeichert.")
                st.rerun()
            except (ValueError, OSError) as exc:
                st.error(str(exc))
    entries = dashboard()
    for entry in entries:
        with st.expander(entry["url"], expanded=False):
            st.write(f"Snapshots: {entry['snapshots']} · Seiten: {entry['pages']} · "
                     f"Dokumentlinks: {entry['documents']}")
            current = get_capture(entry["id"])
            mode = st.selectbox("Erfassungsmodus", options=list(MODES),
                format_func=lambda m: MODES[m], index=list(MODES).index(current["mode"]),
                key=f"mode_{entry['id']}")
            with st.expander("Browser-Einstellungen"):
                selector = st.text_input("CSS-Selektor, auf den gewartet werden soll",
                    value=current["wait_selector"], key=f"selector_{entry['id']}")
                delay = st.number_input("Zusätzliche Wartezeit in Millisekunden", min_value=0,
                    max_value=30000, value=current["wait_ms"], step=500,
                    key=f"delay_{entry['id']}")
            if mode != STATIC:
                st.info("Browsermodus benötigt Playwright und Chromium.")
            if st.button("Erfassungseinstellungen speichern", key=f"settings_{entry['id']}"):
                try:
                    set_settings(entry["id"],mode,selector,int(delay))
                    st.success("Einstellungen gespeichert.")
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))
            deletion = st.checkbox("Auch alle gespeicherten Snapshots dieser Website löschen",
                                   key=f"hist_{entry['id']}")
            confirm = st.checkbox("Entfernung bestätigen", key=f"confirm_{entry['id']}")
            if st.button("Website entfernen", key=f"remove_{entry['id']}", disabled=not confirm):
                remove_site(entry["id"], delete_history=deletion)
                st.success("Website entfernt.")
                st.rerun()
    st.caption("Ohne Löschen der Historie bleiben ältere Snapshots in der Datenbank erhalten, "
               "sind nach Entfernen der Website aber über die Oberfläche nicht mehr zugänglich.")

with tab_snapshots:
    options = dict(sites())
    if not options:
        st.info("Bitte zuerst unter «Websites verwalten» eine Website hinzufügen.")
    else:
        st.subheader("Snapshot-Zentrale")
        left, right = st.columns([3, 2], vertical_alignment="bottom")
        with left:
            site_id = st.selectbox("Website", list(options), format_func=lambda i:options[i],
                                   key="snapshot_site")
        capture = get_capture(site_id)
        with right:
            st.caption(f"Erfassung: {MODES[capture['mode']]} · "
                       "Einstellungen unter «Websites verwalten»")

        history = runs(site_id)
        with st.container(border=True):
            st.markdown("**Neuen Snapshot starten**")
            setup_left, setup_right = st.columns([3, 2], vertical_alignment="bottom")
            with setup_left:
                snap_kind = st.radio("Snapshot-Typ", ["full","partial"],
                    format_func=lambda x:"Full / Baseline" if x=="full" else "Partial / Delta",
                    horizontal=True, key="snapshot_kind")
            with setup_right:
                limit = st.number_input("Maximal besuchte URLs", min_value=10,
                    max_value=20000, value=1000, step=100, key="snapshot_limit")
            st.caption("Full entdeckt Seiten über Sitemaps und Links; Partial prüft bereits "
                       "bekannte URLs. Pro Website ist höchstens ein Job gleichzeitig möglich.")
            job_controls(site_id, options[site_id], int(limit), snap_kind)

        st.markdown("**Snapshot-Archiv**")
        if not history:
            st.info("Für diese Website sind noch keine Snapshots gespeichert.")
        else:
            archive_rows = []
            for row in history:
                j = snapshot_job(row[0])
                start_time = datetime.fromisoformat(j["started_at"]) if j else None
                end_time = datetime.fromisoformat(j["ended_at"]) if j and j["ended_at"] else None
                seconds = max(0,int((end_time-start_time).total_seconds())) if start_time and end_time else None
                info = json.loads(j["progress"] or "{}") if j else {}
                archive_rows.append({
                    "ID":row[0], "Typ":kind(row[0])[0],
                    "Datum (UTC)":row[1].replace("T"," ")[:19],
                    "Status":"Abgeschlossen" if row[2]=="complete" else "Unvollständig" if row[2]=="partial" else row[2],
                    "Dauer":f"{seconds//3600:02d}:{seconds//60%60:02d}:{seconds%60:02d}" if seconds is not None else "—",
                    "URLs":info.get("discovered","—"),"Seiten":info.get("pages","—"),
                    "Dokumente":info.get("documents","—"),
                    "Fehler":len(json.loads(row[3] or "[]"))
                })
            st.dataframe(archive_rows, hide_index=True, width="stretch",
                         height=min(360,36*(len(archive_rows)+1)+8))
            detail_id = st.selectbox("Zusammenfassung und Fehlerprotokoll",
                [r[0] for r in history], key="snapshot_detail",
                format_func=lambda i:f"Snapshot #{i} · {kind(i)[0]}")
            detail_row = next(row for row in history if row[0]==detail_id)
            job = snapshot_job(detail_id)
            info = json.loads(job["progress"] or "{}") if job else {}
            issues = json.loads(detail_row[3] or "[]")
            with st.container(border=True):
                st.markdown(f"**Snapshot #{detail_id} – Job-Zusammenfassung**")
                if job:
                    started = datetime.fromisoformat(job["started_at"])
                    ended = datetime.fromisoformat(job["ended_at"]) if job["ended_at"] else None
                    duration = (ended-started).total_seconds() if ended else info.get("duration_seconds")
                    st.caption(f"Job #{job['id']} · {job['state']} · "
                               f"Start: {started.strftime('%d.%m.%Y %H:%M:%S')} UTC · "
                               f"Ende: {ended.strftime('%d.%m.%Y %H:%M:%S') if ended else '—'} UTC")
                    if duration is not None:
                        duration = max(0,int(duration))
                        st.write(f"**Gesamtlaufzeit:** {duration//3600:02d}:"
                                 f"{duration//60%60:02d}:{duration%60:02d}")
                else:
                    st.caption("Für diesen älteren Snapshot wurden keine Job-Zeitdaten gespeichert.")
                st.caption(f"Snapshot-Typ: {kind(detail_id)[0]} · "
                           f"Erfassungsstatus: {'Abgeschlossen' if detail_row[2]=='complete' else 'Unvollständig' if detail_row[2]=='partial' else detail_row[2]}")
                if info:
                    st.caption(f"Modus: {info.get('capture_mode','nicht erfasst')} · "
                               f"URL-Limit: {info.get('visit_limit','nicht erfasst')} · "
                               f"Letzte Phase: {info.get('phase','—')} · "
                               f"URL: {info.get('site_url', options[site_id])}")
                values = [
                    ("Entdeckte URLs","discovered"),("Besuchte URLs","visited"),
                    ("Archivierte Seiten","pages"),("Dokumente","documents"),
                    ("Noch offen","pending"),("Übersprungen","skipped"),
                    ("Sitemaps","sitemaps"),("Änderungen","changed")]
                st.dataframe([{"Kennzahl":name,"Wert":info.get(key,"Nicht vorhanden")}
                              for name,key in values],hide_index=True,
                             width="stretch",height=320)
                if info.get("limit_warnings"):
                    st.warning("Erreichte Schutzlimits: " + " · ".join(info["limit_warnings"]))
                    st.caption("Abgewiesene URL-Kandidaten nach Ursache: "
                               + json.dumps(info.get("excluded_limits",{}),ensure_ascii=False))
                if info.get("snapshot_kind")=="partial":
                    st.caption(f"Full-Baseline: #{info.get('full_baseline_id','—')} · "
                               f"Änderungen zur Full-Baseline: {info.get('changed_since_full','—')}")
                with st.expander(f"Fehler- und Warnungsprotokoll ({len(issues)})",
                                 expanded=bool(issues)):
                    if issues:
                        st.dataframe([{"Nr.":i,"Meldung":msg}
                            for i,msg in enumerate(issues,1)],hide_index=True,
                            width="stretch",height=min(500,40*len(issues)+40))
                        st.download_button("Fehlerprotokoll als JSON herunterladen",
                            json.dumps({"snapshot_id":detail_id,"errors":issues},
                                       ensure_ascii=False,indent=2),
                            file_name=f"websnapshot_{detail_id}_errors.json",
                            mime="application/json",key=f"download_errors_{detail_id}")
                    else:
                        st.success("Keine protokollierten Fehler oder Warnungen.")
                st.download_button("Job-Zusammenfassung als JSON herunterladen",
                    json.dumps({"snapshot_id":detail_id,"kind":kind(detail_id)[0],
                                "status":detail_row[2],"job":job,
                                "errors":issues},ensure_ascii=False,indent=2),
                    file_name=f"websnapshot_{detail_id}_summary.json",
                    mime="application/json",key=f"download_summary_{detail_id}")


            section_compare, section_documents, section_quality, section_manage = st.tabs(
                ["Änderungen vergleichen", "Dokumente", "Crawl-Diagnose", "Verwaltung"])

            with section_compare:
                if len(history) < 2:
                    st.info("Für einen Vergleich werden zwei Snapshots benötigt.")
                else:
                    ids = [row[0] for row in history]
                    older, newer = st.columns(2)
                    old_id = older.selectbox("Ausgangs-Snapshot", ids, index=1,
                                            key="compare_old")
                    new_id = newer.selectbox("Vergleichs-Snapshot", ids, index=0,
                                            key="compare_new")
                    if old_id == new_id:
                        st.info("Bitte zwei unterschiedliche Snapshots auswählen.")
                    else:
                        changes = compare(old_id, new_id)
                        st.metric("Erkannte Textunterschiede", len(changes))
                        st.download_button("HTML-Änderungsbericht herunterladen",
                            report(changes, old_id, new_id),
                            file_name=f"websnapshot_{old_id}_{new_id}.html",
                            mime="text/html", key="comparison_export")
                        st.caption("Fehlende Seiten sind nicht automatisch gelöscht.")
                        for item in changes:
                            with st.expander(f"{item['kind'].upper()} · {item['url']}"):
                                st.code(item["diff"] or "Kein Text-Diff", language="diff")

            with section_documents:
                doc_run = st.selectbox("Dokumentinventar", [r[0] for r in history],
                                       key="document_run")
                docs = list_documents(doc_run)
                st.caption("PDF- und Word-Dateien werden erst nach expliziter Auswahl "
                           "heruntergeladen. Änderungsstatus basiert auf HTTP-Metadaten.")
                if not docs:
                    st.info("Für diesen Snapshot ist keine Dokumentliste vorhanden.")
                else:
                    st.dataframe([
                        {"Dokument":d["url"], "Status":d["status"],
                         "Grösse (HTTP)":d["length"] or "Unbekannt",
                         "Gespeichert":bool(d["downloaded"])}
                        for d in docs], hide_index=True, width="stretch", height=420)
                    chosen_docs = st.multiselect("Dokumente auswählen",
                        [d["url"] for d in docs], key="selected_documents")
                    layout = st.radio("Ablage", ["Website-Ordnerstruktur", "Flacher Ordner"],
                                      horizontal=True, key="document_layout")
                    if st.button(f"{len(chosen_docs)} Dokumente herunterladen",
                                 disabled=not chosen_docs, key="download_documents"):
                        outcomes = download_selected(doc_run, chosen_docs,
                                                     flat=layout=="Flacher Ordner")
                        for item in outcomes:
                            if "error" in item:
                                st.error(f"{item['url']}: {item['error']}")
                            else:
                                st.success(f"Gespeichert: {item['path']}")
                        st.caption("Download-Verzeichnis: .data/downloads")

            with section_quality:
                diagnostic_id = st.selectbox("Snapshot für Diagnose",
                    [r[0] for r in history], key="diagnostic_run")
                diag = summary(diagnostic_id)
                quality = diag["quality"]
                if quality:
                    st.write(f"**Erfassungsstatus:** {quality[10]}")
                    metrics = st.columns(4)
                    for column,label,value in zip(metrics,
                        ["URLs bekannt","Besucht","Archiviert","Offen"],
                        [quality[1],quality[2],quality[3],quality[5]]):
                        column.metric(label,value)
                    if quality[9]:
                        st.warning("Sicherheitslimit erreicht: Erfassung unvollständig.")
                    st.caption(f"Inhaltsduplikate: {quality[8]} · Fehler: {quality[7]}")
                else:
                    st.info("Für diesen älteren Snapshot sind keine Diagnosedaten vorhanden.")
                with st.expander("Quellen, Ausschlüsse und URL-Muster"):
                    st.write("Quellen", diag["sources"])
                    st.write("Zustände", diag["statuses"])
                    st.write("Ausschlüsse", diag["reasons"])
                    patterns_left, patterns_right = st.columns(2)
                    with patterns_left:
                        st.dataframe([{"Pfad":p,"Varianten":n} for p,n in diag["paths"]],
                                     hide_index=True,width="stretch")
                    with patterns_right:
                        st.dataframe([{"Parameter":p,"Vorkommen":n}
                                      for p,n in diag["parameters"]],
                                     hide_index=True,width="stretch")

            with section_manage:
                st.caption("Full-Snapshots können nur gelöscht werden, wenn keine "
                           "abhängigen Delta-Snapshots vorhanden sind.")
                remove_id = st.selectbox("Snapshot zum Löschen",
                    [r[0] for r in history], key="remove_snapshot",
                    format_func=lambda i:f"#{i} · {kind(i)[0]}")
                confirm = st.checkbox("Dauerhafte Löschung bestätigen",
                                      key="confirm_snapshot")
                if st.button("Snapshot löschen", key="delete_snapshot",
                             disabled=not confirm or running()>0):
                    try:
                        remove_snapshot(site_id,remove_id)
                        st.success("Snapshot gelöscht.")
                        st.rerun()
                    except ValueError as exc:
                        st.error(str(exc))

with tab_map:
    st.subheader("Sitemap / erfasste Seiten")
    options = dict(sites())
    if not options:
        st.info("Bitte zuerst eine Website hinzufügen.")
    else:
        chosen = st.selectbox("Website",list(options),format_func=lambda i:options[i],key="map_site")
        map_history = runs(chosen)
        if not map_history:
            st.info("Noch kein Snapshot erfasst.")
        else:
            selected_run = st.selectbox("Snapshot", [r[0] for r in map_history], key="map_run")
            import sqlite3
            from websnapshot.core import database
            pages = effective_pages(selected_run)
            top_left, top_right = st.columns([3, 2], vertical_alignment="bottom")
            top_left.caption(f"{len(pages)} HTML-Seiten · inklusive geerbter Baseline")
            with top_right:
                table_height = st.select_slider("Tabellenhöhe", options=[350, 550, 800, 1100, 1500],
                                                value=800, format_func=lambda x: f"{x} px",
                                                key="sitemap_height")
            table = [{"Pfad":urlsplit(url).path or "/",
                      "Titel":title,"URL":url,"Öffnen":url,
                      "Zeichen":len(content)}
                     for url,(title,content,digest) in sorted(pages.items())]
            st.dataframe(
                table, hide_index=True, width="stretch", height=table_height,
                row_height=32,
                column_order=["Pfad", "Titel", "Zeichen", "Öffnen", "URL"],
                column_config={
                    "Pfad":st.column_config.TextColumn("Pfad",width="medium"),
                    "Titel":st.column_config.TextColumn("Seitentitel",width="large"),
                    "Zeichen":st.column_config.NumberColumn("Zeichen",format="%d",width="small"),
                    "Öffnen":st.column_config.LinkColumn("Original",display_text="Öffnen ↗",width="small"),
                    "URL":st.column_config.TextColumn("URL",width="large")
                })
            st.caption("Die Tabelle nutzt die ganze Seitenbreite. Über das Symbol rechts oben "
                       "in der Tabelle kannst du die Vollbildansicht öffnen.")


with tab_system:
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
