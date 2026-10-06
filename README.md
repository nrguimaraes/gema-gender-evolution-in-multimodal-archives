# GEMA -- Gender Evolution in Multimodal Archives

A longitudinal study of women's representation in Portuguese sports media (1996--2024), combining NLP protagonist detection and computer vision analysis of front-page covers.

## Live Demo

The interactive dashboard is publicly available at:

**https://gema-dashboard-npu4gb6tgvsmmkw23bsvqz.streamlit.app/**

## Repository Structure

```
gema-gender-evolution-in-multimodal-archives/
  pipeline/       -- crawlers, NLP classifiers, CV pipeline, evaluation
  dashboard/      -- Streamlit dashboard (live demo above)
  data/
    annotations/  -- manual face-level annotations (90 covers, 383 faces)
    capas/        -- cover metadata JSON files (images not included)
```

## Data

- **Text corpus**: 198,771 sports articles from 3 outlets (A Bola, Record, O Jogo), retrieved via [Arquivo.pt](https://arquivo.pt), spanning 1996--2024
- **Cover corpus**: 11,331 front-page cover images from [VerCapas.com](https://www.vercapas.com) (images not included due to size; reproducible via `pipeline/crawlers/capaExtractor.py`)

## Pipeline

The pipeline has two main components:

- **NLP**: protagonist detection using a WikiNeural 80/20 weighted ensemble + Stanza morphological tagger, with Wikidata entity linking for gender inference
- **CV**: face detection (RetinaFace) + gender classification (DeepFace) on cover images

See [`pipeline/README.md`](pipeline/README.md) for full details.

## Dashboard

The Streamlit dashboard allows exploration of 28 years of women's representation trends. See [`dashboard/README.md`](dashboard/README.md) to run locally.

## Annotations

Manual annotations used for pipeline evaluation are in `data/annotations/`:

| File | Description |
|------|-------------|
| `Manual_Annotation_bbox.csv` | Face-level annotations for 90 covers (383 faces) |
| `gema_accuracy_audit_90_covers.csv` | Accuracy audit results for the CV pipeline |
