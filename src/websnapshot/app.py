"""Streamlit user interface for local snapshots."""
import json
import streamlit as st

try:
    from websnapshot.core import add_site, sites, runs, snapshot, compare, report
except ModuleNotFoundError:
    from core import add_site, sites, runs, snapshot, compare, report

st.set_page_config(page_title="WebSnapshot", page_icon="📸", layout="wide")
st.title("WebSnapshot")
st.caption("Manuelle Website-Snapshots und Änderungsberichte · v0.1.0")

with st.form("site"):
    url = st.text_input("Website hinzufügen (https://...)")
    if st.form_submit_button("Website speichern"):
        try:
            add_site(url)
            st.success("Website gespeichert")
        except (ValueError, OSError) as exc:
            st.error(str(exc))

options = dict(sites())
if not options:
    st.info("Füge zuerst eine Website hinzu.")
else:
    site = st.selectbox("Website", options=list(options), format_func=lambda x: options[x])
    limit = st.number_input("Maximale Seitenzahl", min_value=1, max_value=200, value=30)
    depth = st.slider("Linktiefe", min_value=0, max_value=5, value=2)
    if st.button("Neuen Snapshot erstellen", type="primary"):
        with st.spinner("Website wird untersucht …"):
            try:
                run, count, errors = snapshot(site, options[site], int(limit), depth)
                st.success(f"Snapshot {run}: {count} Seiten gespeichert")
                if errors:
                    st.warning(f"{len(errors)} URLs konnten nicht verarbeitet werden")
                    with st.expander("Fehlerdetails"):
                        st.code("\n".join(errors))
            except (ValueError, OSError) as exc:
                st.error(str(exc))
    history = runs(site)
    st.subheader("Snapshot-Archiv")
    st.dataframe([{"ID": row[0], "Datum UTC": row[1], "Status": row[2],
                   "Abruffehler": len(json.loads(row[3]))} for row in history], hide_index=True)
    if len(history) > 1:
        st.subheader("Vergleichen")
        ids = [row[0] for row in history]
        c1, c2 = st.columns(2)
        with c1:
            old = st.selectbox("Älterer Snapshot", ids, index=1)
        with c2:
            new = st.selectbox("Neuerer Snapshot", ids, index=0)
        if old != new:
            changes = compare(old, new)
            st.write(f"**{len(changes)} Unterschiede**")
            for change in changes:
                with st.expander(f"{change['kind'].upper()} · {change['url']}"):
                    st.code(change["diff"] or "Kein Text-Diff", language="diff")
            st.download_button("HTML-Änderungsbericht", report(changes, old, new),
                               file_name=f"websnapshot_{old}_{new}.html", mime="text/html")
            st.caption("Missing bedeutet nicht nachweislich gelöscht.")
        else:
            st.info("Bitte zwei unterschiedliche Snapshots wählen.")
