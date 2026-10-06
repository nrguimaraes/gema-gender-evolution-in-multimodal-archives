# Dashboard

Interactive demonstrator for the GEMA study, built with Streamlit.

## Live Demo

The dashboard is publicly deployed at:

**https://gema-dashboard-npu4gb6tgvsmmkw23bsvqz.streamlit.app/**

## Run Locally

```bash
pip install -r dashboard/requirements.txt
streamlit run dashboard/app.py
```

The dashboard uses static pre-computed data files (no MongoDB required).

## Files

| File | Description |
|------|-------------|
| `app.py` | Main Streamlit application |
| `db_static.py` | Static data loader (reads from `data/` folder) |
| `wikidata_api.py` | Wikidata enrichment for the Athlete Explorer |
| `requirements.txt` | Python dependencies |
