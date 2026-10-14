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
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[2]
st.set_page_config(page_title="WebSnapshot", page_icon="📸", layout="wide")
st.title("WebSnapshot")
st.caption("Website-Inventarisierung, lokale Snapshots und Änderungsberichte · 0.4.0")

tab_overview, tab_sites, tab_snapshots, tab_map, tab_system = st.tabs(
    ["Dashboard", "Websites verwalten", "Snapshots & Vergleich", "Sitemap", "Updates"])

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
        limit = st.number_input("Sicherheitslimit: maximal besuchte URLs", 10, 20000, 1000,
                                step=100)
        st.caption("Automatische Sitemaps und rekursive Linksuche ohne feste Linktiefe. "
                   "Das Schutzlimit verhindert endlose Crawls. robots.txt wird berücksichtigt.")
        @st.fragment(run_every="2s")
        def show_job():
            job = latest(site_id)
            if job:
                from datetime import timezone
                details = json.loads(job["progress"])
                began = datetime.fromisoformat(job["started_at"])
                until = datetime.fromisoformat(job["ended_at"]) if job["ended_at"] else datetime.now(timezone.utc)
                duration = max(0, int((until-began).total_seconds()))
                st.write(f"**Job #{job['id']} – {job['state']}**")
                cols = st.columns(4)
                for col,label,value in zip(cols,["Laufzeit", "Seiten", "Dokumente", "URLs entdeckt"],
                    [f"{duration} s",details.get("pages","—"),details.get("documents","—"),
                     details.get("discovered","—")]):
                    col.metric(label,value)
                if job["state"] in ("queued","running"):
                    st.info("Snapshot läuft im Hintergrund. Du kannst weiterarbeiten.")
                elif job["state"] in ("failed","interrupted"):
                    st.error(job["message"])
                else:
                    st.success(job["message"])
            return job
        current_job = show_job()
        if st.button("Neuen Snapshot im Hintergrund starten", type="primary",
                     disabled=bool(current_job and current_job["state"] in ("queued","running"))):
            started, job_id = launch(site_id,options[site_id],int(limit))
            if started:
                st.success(f"Job #{job_id} gestartet.")
            else:
                st.warning(f"Für diese Website läuft Job #{job_id} bereits.")
            st.rerun()
        history = runs(site_id)
        st.subheader("Snapshot-Verlauf")
        st.dataframe([{"ID":r[0],"Zeitpunkt (UTC)":r[1],"Status":r[2],
                       "Fehler":len(json.loads(r[3]))} for r in history],
                     hide_index=True, use_container_width=True)
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
            with sqlite3.connect(database()) as db:
                entries = db.execute("SELECT url,title FROM pages WHERE run_id=? ORDER BY url",
                                     (selected_run,)).fetchall()
            st.caption(f"{len(entries)} archivierte HTML-Seiten. Die Gliederung folgt URL-Pfaden, "
                       "nicht zwingend der tatsächlichen Website-Navigation.")
            query = st.text_input("URL oder Titel suchen",key="sitemap_search")
            folders = {}
            for url,title in entries:
                parts = [s for s in urlsplit(url).path.split("/") if s]
                folders.setdefault(parts[0] if parts else "Startseite", []).append((url,title))
            for folder,values in sorted(folders.items()):
                subset = [(u,t) for u,t in values if query.casefold() in (u+" "+t).casefold()]
                if not subset:
                    continue
                with st.expander(f"📁 {folder} ({len(subset)})",expanded=bool(query)):
                    for url,title in subset:
                        left,right=st.columns([6,1])
                        left.write(f"📄 {title or url}")
                        left.caption(url)
                        right.link_button("Öffnen ↗",url)

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
