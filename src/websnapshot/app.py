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
from websnapshot.jobs import launch, latest, running, recover_interrupted
from websnapshot.settings import MODES, STATIC, get as get_capture, set_settings
from websnapshot.versions import kind, effective_pages, remove_snapshot
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[2]
st.set_page_config(page_title="WebSnapshot", page_icon="📸", layout="wide")
st.title("WebSnapshot")
st.caption("Website-Inventarisierung, lokale Snapshots und Änderungsberichte · 0.6.0")

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
            st.metric("Textänderungen zum Vorgänger",info.get("changed",0))
            st.caption(f"Vergleich mit Snapshot #{info.get('baseline_id','?')} inklusive geerbter Inhalte")
        else:
            st.caption(f"{info.get('discovered',0)} URLs entdeckt · {info.get('visited',0)} besucht · Phase: {info.get('phase','Wartet')}")
        if active:
            st.info("Für diese Website läuft bereits ein Job.")
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
            st.progress(min(1,max(0,percent/100)),text=f"Partial: {percent:.1f}% · {info.get('changed',0)} Änderungen zum Vorgänger")
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
        for entry in overview:
            age = entry["oldest_age"]
            marker = "🔴" if age is not None and age > 30 else "🟢" if age is not None else "⚪"
            st.subheader(entry["url"])
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Seiten", entry["pages"])
            c2.metric("Dokumentlinks", entry["documents"])
            c3.metric("Snapshots", entry["snapshots"])
            c4.metric("Archivierter Text", f"{entry['content_bytes']/1048576:.2f} MB")
            st.write(f"{marker} Ältester Snapshot: **{entry['oldest'] or 'Noch keiner'}**"
                     + (f" (**{age} Tage alt**)" if age is not None else ""))
            st.caption(f"Letzter Snapshot: {entry['newest'] or '—'} · "
                       f"Bekannte URLs: {entry['discovered']} · Noch offen: {entry['pending']}")
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
            st.caption(f"{len(pages)} HTML-Seiten inkl. geerbter Baseline")
            table = [{"Pfad":urlsplit(url).path or "/",
                      "Titel":title,"URL":url,"Öffnen":url,
                      "Zeichen":len(content)}
                     for url,(title,content,digest) in sorted(pages.items())]
            st.dataframe(table, hide_index=True,use_container_width=True,
                column_config={"Öffnen":st.column_config.LinkColumn("Originalseite",
                                  display_text="Öffnen")})

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
