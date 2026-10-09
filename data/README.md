# Data

This folder contains the corpus, pipeline outputs, and annotations used in the paper.

## Structure

```
data/
  annotations/
    Manual_Annotation_bbox.csv          -- face-level manual annotations (90 covers, 383 faces)
    gema_accuracy_audit_90_covers.csv   -- CV pipeline accuracy audit (30 covers per newspaper)
  capas/
    images/    -- 11,331 front-page cover images (JPG), named <outlet>_<YYYY-MM-DD>.jpg
    metadata/  -- one JSON per cover with crawl metadata (source, date, original URL)
  raw/
    articles/  -- raw article JSON files as extracted from Arquivo.pt, one per outlet per year
    links/     -- article URL lists collected by the link crawler
  cleaned/     -- cleaned article JSON files (input to enrichment step)
  enriched/    -- articles with publication date added (publication_date + date_extraction_method fields);
                  used as input to the NLP classifier
  processed/
    image_analysis/             -- final visual pipeline results (RetinaFace + YOLOv8n)
    processed_wikineural_final/ -- final NLP classification results (WikiNeural 80/20 ensemble)
```

## Text Articles

The 198,771 text articles were retrieved from [Arquivo.pt](https://arquivo.pt) using the
crawlers in `pipeline/crawlers/`. Files in `raw/articles/` follow the naming convention
`<outlet>_<YYYY>.json`. The `cleaned/` folder contains the cleaned version and `enriched/`
adds publication date metadata (`publication_date`, `date_extraction_method`), used as input
to the classifier.

## Cover Images

The 11,331 front-page cover images are in `data/capas/images/`, named `<outlet>_<YYYY-MM-DD>.jpg`
(e.g. `a-bola_2016-05-11.jpg`). They were sourced from [VerCapas.com](https://www.vercapas.com).

## Annotations

The annotation CSV files in `data/annotations/` use `Source` (e.g. `A Bola`) and `Date`
(e.g. `2016-05-11`) columns. To map a CSV row to its cover image:

```python
filename = source.lower().replace(" ", "-") + "_" + date + ".jpg"
# e.g. "A Bola" + "2016-05-11" → "a-bola_2016-05-11.jpg"
```

| File | Description | Records |
|------|-------------|---------|
| `Manual_Annotation_bbox.csv` | Face-level manual annotations for the bbox audit | 383 faces across 90 covers |
| `gema_accuracy_audit_90_covers.csv` | Pipeline accuracy audit (30 covers per newspaper) | 90 covers |

### Sample annotation row

```
Source,Date,Boxes,Women,Men,Notes
A Bola,2016-05-11,2,0,2,
```
