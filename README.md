# GEMA

A longitudinal study of women's representation in Portuguese sports media (1998-2026), combining NLP protagonist detection and computer vision analysis of front-page covers.

## Quick Start

The processed results are already included in this repository; no need to re-run the pipeline.

**Explore the dashboard (no setup required):**

The interactive dashboard is publicly available at:
**https://gema-dashboard-npu4gb6tgvsmmkw23bsvqz.streamlit.app/**

**Run the dashboard locally:**

```bash
git clone https://github.com/nrguimaraes/gema-gender-evolution-in-multimodal-archives.git
cd gema-gender-evolution-in-multimodal-archives/demo
pip install -r requirements.txt
streamlit run app.py
```

**Use the data directly:**

```python
import json

# NLP results: women's representation in articles, one outlet/year
with open("data/processed/processed_wikineural_final/abolapt_2020.json", encoding="utf-8") as f:
    classified = json.load(f)  # list of articles, each with "gender_analysis" verdict

# CV results: face detection and gender classification on cover images
with open("data/processed/image_analysis/gender_vision_results_retinaface.json", encoding="utf-8") as f:
    vision = json.load(f)  # keyed by filename, e.g. vision["a-bola_2022-02-18.jpg"]
```

See [Query Examples](#query-examples) below for more.

## Live Demo

The interactive dashboard is publicly available at:

**https://gema-dashboard-npu4gb6tgvsmmkw23bsvqz.streamlit.app/**

![GEMA dashboard](docs/demo_screenshot.png)

## Description

**What this project does:** GEMA is a longitudinal dataset and analysis pipeline covering nearly three decades (1998-2026) of women's representation in Portuguese sports media. It combines a large-scale text corpus of sports articles with a corpus of front-page newspaper cover images, processed through NLP and computer vision pipelines to measure how often women appear as protagonists in sports journalism.

**Who it is for:**

- Researchers studying gender representation and media bias
- NLP and computer vision researchers working on Portuguese-language sports media
- Journalists and media analysts studying diversity in sports coverage
- Social scientists tracking longitudinal trends in sports journalism

**What problem it solves:** Women's representation in sports media is systematically understudied, in part because analysing it at scale requires processing both text and images across decades of content. GEMA provides ready-to-use processed results, a reproducible pipeline, and an interactive dashboard, making it straightforward to explore or build on nearly three decades of data from major Portuguese sports newspapers.

## Project Status

This project is currently completed and stable. The dataset and pipeline represent the full study period (1998-2026) as described in the associated paper.

## Dataset Statistics

| Corpus | Size | Sources | Period |
|--------|------|---------|--------|
| Text articles | 198,777 articles | 7 outlets (A Bola, Record, O Jogo, Euronews, Notícias ao Minuto, Sapo, Zap Aeiou) | 1998-2024 |
| Cover images | 11,331 images | 3 newspapers (A Bola, Record, O Jogo) | 2016-2026 |
| Manual annotations (bbox) | 30 covers, 95 faces | 3 newspapers | 2016-2026 |
| Accuracy audit annotations | 383 face comparisons across 90 covers | 3 newspapers | 2016-2026 |

## Repository Structure

```
gema-gender-evolution-in-multimodal-archives/
  pipeline/       crawlers, NLP classifiers, CV pipeline, evaluation
  demo/           Streamlit dashboard (live demo above, Docker support included)
  data/
    annotations/  manual bbox annotations (30 covers) + accuracy audit (90 covers, 383 faces)
    capas/
      images/     11,331 cover images (JPG), named <outlet>_<YYYY-MM-DD>.jpg
      metadata/   one JSON per cover with crawl metadata (source, date, original URL)
    raw/
      articles/   raw article JSON files, one per outlet per year
      links/      article URL lists from the link crawler
    cleaned/      cleaned article JSON files
    enriched/     articles with publication date added (input to NLP classifier)
    processed/
      image_analysis/             final CV pipeline results (RetinaFace + YOLOv8n)
      processed_wikineural_final/ final NLP results (WikiNeural 80/20 ensemble)
```

See [`data/README.md`](data/README.md) for full details, including data format and annotated examples.

## Data Format

### Article records (`data/raw/articles/` and `data/processed/processed_wikineural_final/`)

Files follow the naming convention `<outlet>_<YYYY>.json` (e.g. `abolapt_2020.json`), each containing a list of article objects.

| Field | Description |
|-------|-------------|
| `link` | Original article URL via Arquivo.pt |
| `source` | Outlet identifier (e.g. `abola.pt`) |
| `year` | Publication year |
| `title` | Article headline |
| `body_text` | Full article body |
| `publication_date` | Extracted publication date (ISO format, added in enrichment step) |
| `date_extraction_method` | Method used to extract the date |
| `gender_analysis` | NLP classification result (added by the classifier) |
| `gender_analysis.verdict` | `"Masculino"`, `"Feminino"`, or `"Neutro/Equilibrado"` |
| `gender_analysis.confidence_scores` | `{"F": float, "M": float, "signals_count": {...}}` |
| `gender_analysis.details.protagonists` | `{"feminine": [...], "masculine": [...]}` named entities |

### Cover image results (`data/processed/image_analysis/gender_vision_results_retinaface.json`)

A single JSON object keyed by filename (e.g. `"a-bola_2022-02-18.jpg"`), each entry containing a list of detected faces.

| Field | Description |
|-------|-------------|
| `gender` | `"Man"` or `"Woman"` |
| `gender_confidence` | Confidence score (0-100) |
| `face_confidence` | RetinaFace detection confidence (0-1) |
| `bbox` | Bounding box `[x1, y1, x2, y2]` in pixels |
| `cover_coverage_percentage` | Fraction of cover area occupied by this face |

### Cover metadata (`data/capas/metadata/`)

One JSON file per cover image (e.g. `a-bola_2022-02-18.jpg.json`).

| Field | Description |
|-------|-------------|
| `source` | Newspaper slug (e.g. `a-bola`) |
| `date` | Cover date (ISO format) |
| `page_url` | VerCapas.com page URL |
| `img_url` | Direct image URL |
| `resolution` | Image resolution tier |

## Pipeline

The pipeline has two main components:

- **NLP**: protagonist detection using a WikiNeural 80/20 weighted ensemble + Stanza morphological tagger, with Wikidata entity linking to identify female protagonists
- **CV**: face detection (RetinaFace) + gender classification (DeepFace) on cover images

See [`pipeline/README.md`](pipeline/README.md) for full details.

## Annotations

Manual annotations used for pipeline evaluation are in `data/annotations/`:

| File | Description |
|------|-------------|
| `Manual_Annotation_bbox.csv` | Bounding box annotations for 30 covers (95 faces) |
| `gema_accuracy_audit_90_covers.csv` | Face-level accuracy audit for 90 covers (383 face comparisons) |

The `Filename` column in both files maps each row directly to its cover image in `data/capas/images/`.

## Loading the Data

```python
import json, csv

# Load raw articles for one outlet/year
with open("data/raw/articles/abolapt_2020.json", encoding="utf-8") as f:
    articles = json.load(f)  # list of {"link", "source", "year", "title", "body_text"}

# Load NLP classification results for the same outlet/year
with open("data/processed/processed_wikineural_final/abolapt_2020.json", encoding="utf-8") as f:
    classified = json.load(f)  # same fields + "publication_date", "gender_analysis"

# Load CV pipeline results for all covers
with open("data/processed/image_analysis/gender_vision_results_retinaface.json", encoding="utf-8") as f:
    vision = json.load(f)  # keyed by filename, e.g. vision["a-bola_2022-02-18.jpg"]

# Load cover annotations (Filename column links to data/capas/images/)
with open("data/annotations/Manual_Annotation_bbox.csv", encoding="utf-8") as f:
    annotations = list(csv.DictReader(f))
```

## Query Examples

**1. Count articles with female protagonists per year for one outlet**

```python
import json
from collections import Counter

with open("data/processed/processed_wikineural_final/abolapt_2020.json", encoding="utf-8") as f:
    articles = json.load(f)

counts = Counter(a["gender_analysis"]["verdict"] for a in articles if "gender_analysis" in a)
print(counts)  # Counter({'Masculino': 1820, 'Neutro': 312, 'Feminino': 48})
```

**2. Get all named female protagonists across an outlet/year**

```python
female_names = []
for article in articles:
    protagonists = article.get("gender_analysis", {}).get("details", {}).get("protagonists", {})
    female_names.extend(protagonists.get("feminine", []))

print(set(female_names))
```

**3. Find covers where the pipeline detected at least one woman**

```python
import json

with open("data/processed/image_analysis/gender_vision_results_retinaface.json", encoding="utf-8") as f:
    vision = json.load(f)

covers_with_women = [
    filename for filename, entry in vision.items()
    if any(face["gender"] == "Woman" for face in entry.get("full_image", []))
]
print(f"{len(covers_with_women)} covers with at least one woman detected")
```

**4. Compute the share of female faces per newspaper**

```python
from collections import defaultdict

stats = defaultdict(lambda: {"total": 0, "women": 0})
for filename, entry in vision.items():
    outlet = filename.split("_")[0]  # e.g. "a-bola"
    for face in entry.get("full_image", []):
        stats[outlet]["total"] += 1
        if face["gender"] == "Woman":
            stats[outlet]["women"] += 1

for outlet, s in stats.items():
    pct = 100 * s["women"] / s["total"] if s["total"] else 0
    print(f"{outlet}: {pct:.1f}% female faces ({s['women']}/{s['total']})")
```
