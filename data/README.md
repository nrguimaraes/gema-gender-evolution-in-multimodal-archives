# Data

This folder contains the corpus, pipeline outputs, and annotations used in the paper.

## Structure

```
data/
  annotations/
    Manual_Annotation_bbox.csv          -- manual face-level annotations (90 covers, 383 faces)
    gema_accuracy_audit_90_covers.csv   -- accuracy audit results for the visual pipeline
  capas/
    images/    -- 11,331 front-page cover images (JPG)
    metadata/  -- one JSON per cover with face detection results (RetinaFace + DeepFace)
  raw/
    articles/  -- raw article JSON files as extracted from Arquivo.pt
    links/     -- article URL lists collected by the link crawler
  cleaned/     -- cleaned article JSON files by outlet and year (input to NLP pipeline)
  enriched/    -- articles with publication date added (publication_date + date_extraction_method fields)
  processed/
    image_analysis/             -- final visual pipeline results (RetinaFace + YOLOv8n)
    processed_wikineural_final/ -- final NLP classification results (WikiNeural 80/20 ensemble)
```

## Text Articles

The 198,771 text articles were retrieved from [Arquivo.pt](https://arquivo.pt) using the
crawlers in `pipeline/crawlers/`. The `cleaned/` folder contains the cleaned version and
`enriched/` contains the Wikidata-enriched version used as input to the classifier.

## Cover Images

The 11,331 front-page cover images are available in `data/capas/images/`.
They were sourced from [VerCapas.com](https://www.vercapas.com).

## Annotations

| File | Description | Records |
|------|-------------|---------|
| `Manual_Annotation_bbox.csv` | Face-level manual annotations for the bbox audit | 383 faces across 90 covers |
| `gema_accuracy_audit_90_covers.csv` | Pipeline accuracy audit (30 covers per newspaper) | 90 covers |
