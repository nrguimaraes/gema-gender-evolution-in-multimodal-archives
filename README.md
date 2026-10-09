# GEMA

A longitudinal study of women's representation in Portuguese sports media (1996--2024), combining NLP protagonist detection and computer vision analysis of front-page covers.

## Live Demo

The interactive dashboard is publicly available at:

**https://gema-dashboard-npu4gb6tgvsmmkw23bsvqz.streamlit.app/**

## Repository Structure

```
gema-gender-evolution-in-multimodal-archives/
  pipeline/       -- crawlers, NLP classifiers, CV pipeline, evaluation
  demo/           -- Streamlit dashboard (live demo above, Docker support included)
  data/
    annotations/  -- manual face-level annotations (90 covers, 383 faces)
    capas/
      images/     -- 11,331 cover images (JPG), named <outlet>_<YYYY-MM-DD>.jpg
      metadata/   -- one JSON per cover with crawl metadata (source, date, original URL)
    raw/
      articles/   -- raw article JSON files, one per outlet per year
      links/      -- article URL lists from the link crawler
    cleaned/      -- cleaned article JSON files
    enriched/     -- articles with publication date added (input to NLP classifier)
    processed/
      image_analysis/             -- final CV pipeline results (RetinaFace + YOLOv8n)
      processed_wikineural_final/ -- final NLP results (WikiNeural 80/20 ensemble)
```

## Data

- **Text corpus**: 198,771 sports articles from 7 outlets, retrieved via [Arquivo.pt](https://arquivo.pt), spanning 1998--2024
- **Cover corpus**: 11,331 front-page cover images from 3 national sports newspapers (A Bola, Record, O Jogo), sourced from [VerCapas.com](https://www.vercapas.com), available in `data/capas/images/`

See [`data/README.md`](data/README.md) for full details, including the CSV-to-image naming convention.

## Pipeline

The pipeline has two main components:

- **NLP**: protagonist detection using a WikiNeural 80/20 weighted ensemble + Stanza morphological tagger, with Wikidata entity linking to identify female protagonists
- **CV**: face detection (RetinaFace) + gender classification (DeepFace) on cover images

See [`pipeline/README.md`](pipeline/README.md) for full details.

## Demo

The Streamlit dashboard allows exploration of 28 years of women's representation trends. See [`demo/README.md`](demo/README.md) to run locally or with Docker.

![GEMA dashboard](docs/demo_screenshot.png)

## Annotations

Manual annotations used for pipeline evaluation are in `data/annotations/`:

| File | Description |
|------|-------------|
| `Manual_Annotation_bbox.csv` | Face-level annotations for 90 covers (383 faces) |
| `gema_accuracy_audit_90_covers.csv` | Accuracy audit results for the CV pipeline |
