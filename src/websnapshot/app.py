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
from websnapshot.jobs import launch, latest, running, recover_interrupted, request_cancel
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
            st.caption(f"{info.get('discovered',0)} URLs entdeckt · {info.get('visited',0)} besucht · Phase: {info.get('phase','Wartet')}")
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
        st.info("Bitte zuerst eine Website hinzufügen.")
    else:
        site_id = st.selectbox("Website auswählen", list(options),
                               format_func=lambda i: options[i])
        capture = get_capture(site_id)
        st.caption(f"Erfassungsmodus: **{MODES[capture['mode']]}** – "
                   "änderbar unter «Websites verwalten».")
        if capture["mode"] != STATIC:
            st.info("Browsermodus rendert JavaScript-Inhalte mit Chromium.")
        limit = st.number_input("Sicherheitslimit: maximal besuchte URLs", 10, 20000, 1000,
                                step=100)
        st.caption("Automatische Sitemaps und rekursive Linksuche ohne feste Linktiefe. "
                   "Das Schutzlimit verhindert endlose Crawls. robots.txt wird berücksichtigt.")
        snap_kind = st.radio("Snapshot-Art",["full","partial"],format_func=lambda x: "Full / Baseline" if x=="full" else "Partial / Delta",horizontal=True)
        job_controls(site_id,options[site_id],int(limit),snap_kind)
        history = runs(site_id)
        st.subheader("Snapshot-Verlauf")
        st.dataframe([{"ID":r[0],"Typ":kind(r[0])[0],"Zeitpunkt (UTC)":r[1],"Status":r[2],
                       "Fehler":len(json.loads(r[3]))} for r in history],
                     hide_index=True, use_container_width=True)
        if history:
            st.subheader("Crawl-Diagnose und Qualität")
            diagnostic_id=st.selectbox("Diagnose zu Snapshot", [r[0] for r in history], key="diagnostic_run")
            diag=summary(diagnostic_id)
            q=diag["quality"]
            if q:
                st.write(f"**Qualitätsstatus:** {q[10]}")
                a,bx,cc,dd=st.columns(4)
                a.metric("Bekannte URLs",q[1])
                bx.metric("Besucht",q[2])
                cc.metric("Archiviert",q[3])
                dd.metric("Offen",q[5])
                if q[9]:
                    st.warning("Erfassungsgrenzen erreicht; Snapshot ist unvollständig.")
                st.caption(f"Duplikate mit gleichem HTML-Text: {q[8]} · Fehler: {q[7]}")
            with st.expander("URL-Herkunft, Ausschlüsse und auffällige Muster"):
                st.write("Quellen",diag["sources"])
                st.write("Zustände",diag["statuses"])
                st.write("Ausschlussgründe",diag["reasons"])
                st.dataframe([{"Pfad":p,"Varianten":n} for p,n in diag["paths"]],hide_index=True)
                st.dataframe([{"Parameter":p,"Vorkommen":n} for p,n in diag["parameters"]],hide_index=True)
        if history:
            st.subheader("Snapshot entfernen")
            remove_id = st.selectbox("Snapshot", [r[0] for r in history],key="remove_snapshot")
            confirm = st.checkbox("Dauerhaft löschen bestätigen",key="confirm_snapshot")
            if st.button("Snapshot löschen", disabled=not confirm or running()>0):
                try:
                    remove_snapshot(site_id,remove_id)
                    st.success("Snapshot entfernt")
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))
        if history:
            st.subheader("PDF- und Word-Dokumente")
            doc_run = st.selectbox("Dokumentinventar aus Snapshot", [r[0] for r in history],
                                   key="document_run")
            docs = list_documents(doc_run)
            if docs:
                st.caption("Beim Snapshot werden nur URLs und, soweit verfügbar, HTTP-Metadaten "
                           "(ETag, Änderungsdatum, Dateigrösse) geprüft. "
                           "Ohne belastbare Metadaten bleibt der Änderungsstatus unbekannt.")
                st.dataframe([{"Dokument":d["url"], "Änderungsstatus":d["status"],
                               "Grösse (HTTP)":d["length"] or "Unbekannt",
                               "Heruntergeladen": bool(d["downloaded"])} for d in docs],
                             hide_index=True, use_container_width=True)
                selected = st.multiselect("Dokumente für Download auswählen",
                                          options=[d["url"] for d in docs])
                mode = st.radio("Ordnerstruktur",["Wie auf der Website","Alle Dateien in einem Ordner"],
                                horizontal=True)
                if st.button(f"{len(selected)} ausgewählte Dokumente herunterladen",
                             disabled=not selected):
                    with st.spinner("Dokumente werden heruntergeladen …"):
                        outcomes = download_selected(doc_run,selected,
                                                      flat=mode.startswith("Alle"))
                    for item in outcomes:
                        if "error" in item:
                            st.error(f"{item['url']}: {item['error']}")
                        else:
                            st.success(f"Gespeichert: {item['path']} ({item['bytes']} Bytes)")
                    st.caption("Zielverzeichnis: .data/downloads; nur ausgewählte Dateien "
                               "werden heruntergeladen. Bestehende Dateinamen werden dabei ersetzt.")
            else:
                st.info("Keine PDF- oder Word-Dokumente für diesen Snapshot inventarisiert. "
                        "Snapshots aus Version 0.2 enthalten noch keine detaillierte Dokumentliste.")
        if len(history) > 1:
            ids = [row[0] for row in history]
            a,b = st.columns(2)
            old_id = a.selectbox("Älterer Snapshot", ids, index=1)
            new_id = b.selectbox("Neuerer Snapshot", ids, index=0)
            if old_id != new_id:
                changes = compare(old_id,new_id)
                st.metric("Unterschiede",len(changes))
                for item in changes:
                    with st.expander(f"{item['kind'].upper()} · {item['url']}"):
                        st.code(item["diff"] or "Kein Text-Diff", language="diff")
                st.download_button("HTML-Änderungsbericht herunterladen",
                                   report(changes,old_id,new_id),
                                   file_name=f"websnapshot_{old_id}_{new_id}.html",
                                   mime="text/html")
                st.caption("Eine fehlende Seite bedeutet nicht, dass sie gelöscht wurde.")

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
