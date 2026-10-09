# Pipeline

This folder contains all code used to build and run the GEMA multimodal pipeline.

> **Note:** Pre-computed results for both the NLP and CV pipelines are already included in `data/processed/`. You only need to run the pipeline scripts if you want to reproduce the results from scratch or extend the analysis to new data.

## Reproduce the Results

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run the NLP classifier on all articles (requires MongoDB)
python classify_articles.py

# 3. Run the CV pipeline on all cover images (requires MongoDB)
python vision/analyze_faces.py

# 4. Evaluate both pipelines against the manual annotations
python evaluation/pipeline_evaluation.py
```

## Structure

```
pipeline/
  crawlers/       -- article and cover crawlers (Arquivo.pt + VerCapas.com)
  classifiers/    -- NLP protagonist classifiers (WikiNeural ensemble, Stanza, mDeBERTa, NLTK)
  vision/         -- CV pipeline (RetinaFace face detection + DeepFace gender classification)
  evaluation/     -- pipeline evaluation scripts
  resources/      -- Portuguese first-name list used by the NLTK baseline
  classify_articles.py  -- batch classifier entry point (runs wikineural_pesos over all articles)
  wikidata_api.py       -- Wikidata enrichment utility
```

## Requirements

```bash
pip install -r requirements.txt
```

Additional infrastructure:
- MongoDB (local or Atlas) for article and cover storage

## Crawlers

| Script | Description |
|--------|-------------|
| `crawlers/linkExtractor.py` | Collects article URLs from Arquivo.pt CDX API |
| `crawlers/articleExtractor.py` | Extracts article content (title, body, date) |
| `crawlers/capaExtractor.py` | Downloads front-page cover images from VerCapas.com |

## NLP Classifiers

The production classifier is the WikiNeural 80/20 weighted ensemble (`classifiers/process_wikineural_pesos.py`), run at scale via `classify_articles.py`.
All classifiers use the concatenation of title and body text as input:
```python
full_text = f"{title}. {body_text}"
```

| Script | Method |
|--------|--------|
| `process_wikineural_pesos.py` | WikiNeural NER -- 80/20 weighted ensemble (production) |
| `process_stanza.py` | Stanza morphological tagging |
| `process_mdeberta.py` | mDeBERTa-v3 zero-shot classification |
| `process_nltk_baseline.py` | NLTK + first-name dictionary baseline |

## Visual Pipeline

1. `vision/analyze_faces.py` -- RetinaFace detection + DeepFace gender classification
2. `vision/process_yolo.py` -- YOLOv8n person detection (used to flag occluded/rear-facing persons)

## Evaluation

`evaluation/pipeline_evaluation.py` -- computes precision, recall and F1 for both NLP and CV pipelines against the manual annotations in `data/annotations/`.
