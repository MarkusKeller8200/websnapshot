# WebSnapshot

Local, manually triggered website snapshots, content comparison and HTML change reports.

## Local installation (Windows/macOS)

Requires Python 3.11+.

```bash
git clone https://github.com/MarkusKeller8200/websnapshot.git
cd websnapshot
python -m venv .venv
```

Activate the environment: Windows PowerShell: `.venv\Scripts\Activate.ps1`; macOS: `source .venv/bin/activate`.

```bash
pip install -e '.[dev]'
streamlit run src/websnapshot/app.py
```

Open http://localhost:8501. Add a public URL, adjust crawl depth and page count, run a manual snapshot, then select two snapshots to generate a report.

Snapshots are stored locally in `.data/` and must not be committed.

**V0.1 limitations:** Static HTML only; no PDF extraction, dynamic JS rendering, AI or scheduling. Missing pages are NOT confirmed deletions. Respect robots.txt, copyright and website usage terms. This is for trusted local use only.

See [Konzept](docs/KONZEPT.md).
