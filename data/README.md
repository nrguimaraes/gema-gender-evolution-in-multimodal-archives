# Data

This folder contains the corpus and annotations used in the paper.

## Structure

```
data/
  annotations/
    Manual_Annotation_bbox.csv          -- manual face-level annotations (90 covers, 383 faces)
    gema_accuracy_audit_90_covers.csv   -- accuracy audit results for the visual pipeline
  capas/
    metadata/   -- one JSON per cover with face detection results (RetinaFace + DeepFace)
    images/     -- cover images (included in this repo)
```

## Cover Images

The 11,331 front-page cover images are available in `data/capas/images/`.
They were sourced from [VerCapas.com](https://www.vercapas.com).

## Text Articles

The 198,771 text articles were retrieved from [Arquivo.pt](https://arquivo.pt) and are stored
in MongoDB. The crawlers in `pipeline/crawlers/` reproduce the full collection pipeline.

## Annotations

| File | Description | Records |
|------|-------------|---------|
| `Manual_Annotation_bbox.csv` | Face-level manual annotations for the bbox audit | 383 faces across 90 covers |
| `gema_accuracy_audit_90_covers.csv` | Pipeline accuracy audit (30 covers per newspaper) | 90 covers |
