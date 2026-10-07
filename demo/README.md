# Demo

Interactive dashboard for the GEMA study, built with Streamlit.

## Live Demo

The dashboard is publicly deployed at:

**https://gema-dashboard-npu4gb6tgvsmmkw23bsvqz.streamlit.app/**

## Run with Docker

```bash
docker build -t gema-demo .
docker run -p 8501:8501 gema-demo
```

Then open http://localhost:8501 in your browser.

## Run Locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

The dashboard uses static pre-computed data files (no MongoDB required).

## Files

| File | Description |
|------|-------------|
| `app.py` | Main Streamlit application |
| `db_static.py` | Static data loader (reads from `data/` folder) |
| `wikidata_api.py` | Wikidata enrichment for the Athlete Explorer |
| `requirements.txt` | Python dependencies |
| `Dockerfile` | Docker image definition |
