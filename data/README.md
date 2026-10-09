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

### Sample article record

**Raw** (`data/raw/articles/abolapt_2000.json`):

```json
{
  "link": "https://arquivo.pt/noFrame/replay/20000511184017/http:/www.abola.pt:80/...",
  "source": "abola.pt",
  "year": "2000",
  "title": "Destaques de quinta-feira",
  "body_text": "OS MELHORES DE «A BOLA» – Rui Jorge divide os méritos pelo grupo..."
}
```

**After NLP classification** (`data/processed/processed_wikineural_final/abolapt_2000.json`):

```json
{
  "link": "https://arquivo.pt/noFrame/replay/20000511184017/http:/www.abola.pt:80/...",
  "source": "abola.pt",
  "year": "2000",
  "title": "Destaques de quinta-feira",
  "publication_date": "2000-05-11",
  "date_extraction_method": "arquivo_pt_proxy",
  "gender_analysis": {
    "verdict": "Masculino",
    "confidence_scores": { "F": 0.08, "M": 0.92 },
    "details": {
      "protagonists": {
        "feminine": [],
        "masculine": ["Nuno Gomes", "Rui Jorge"]
      }
    }
  }
}
```

## Cover Images

The 11,331 front-page cover images are in `data/capas/images/`, named `<outlet>_<YYYY-MM-DD>.jpg`
(e.g. `a-bola_2016-05-11.jpg`). They were sourced from [VerCapas.com](https://www.vercapas.com).

### Sample cover record

`data/capas/images/a-bola_2022-02-18.jpg` (all 3 faces correctly identified by the pipeline):

![A Bola cover 2022-02-18](../docs/cover_example.jpg)

**Crawl metadata** (`data/capas/metadata/a-bola_2022-02-18.jpg.json`):

```json
{
  "source": "a-bola",
  "date": "2022-02-18",
  "page_url": "https://www.vercapas.com/capa/arquivo/a-bola/2022-02-18.html",
  "img_url": "https://imgs.vercapas.com/covers/a-bola/2022/a-bola-2022-02-18-5e0cc2d9.jpg",
  "resolution": "full"
}
```

**After CV pipeline** (entry in `data/processed/image_analysis/gender_vision_results_retinaface.json`):

```json
"a-bola_2022-02-18.jpg": {
  "full_image": [
    {
      "gender": "Man",
      "gender_confidence": 100.0,
      "face_confidence": 1.0,
      "bbox": [126, 99, 243, 283],
      "cover_coverage_percentage": 3.32
    },
    {
      "gender": "Man",
      "gender_confidence": 100.0,
      "face_confidence": 0.97,
      "bbox": [444, 770, 476, 814],
      "cover_coverage_percentage": 0.22
    },
    {
      "gender": "Man",
      "gender_confidence": 99.99,
      "face_confidence": 0.93,
      "bbox": [127, 813, 156, 851],
      "cover_coverage_percentage": 0.17
    }
  ]
}
```

The `bbox` field is `[x1, y1, x2, y2]` in pixels. `cover_coverage_percentage` is the fraction of the cover area occupied by that face.

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
Filename,Source,Date,Boxes,Women,Men,Notes
a-bola_2016-05-11.jpg,A Bola,2016-05-11,2,0,2,
```
