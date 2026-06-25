"""
GEMA — Gender Evolution in Multimodal Archives
Data access layer: server-side MongoDB aggregation pipelines only,
so Python receives pre-aggregated results and stays memory-safe at scale.
"""
import os
import streamlit as st
from pymongo import MongoClient
import pandas as pd

MONGO_URI = os.environ.get("MONGO_URI", "mongodb://172.17.16.1:27017/")
DB_NAME = "estagio_desporto"

# ---------------------------------------------------------------------------
# Database connection
# ---------------------------------------------------------------------------

@st.cache_resource
def get_db():
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    return client[DB_NAME]


# Minimum cover area (%) a face must occupy to be considered an editorial subject.
# Dataset median of cover_coverage_percentage — faces below this are editorial background.
PROMINENCE_THRESHOLD = 0.17


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normalise_source(raw: str) -> str:
    """Normalise raw source strings to display newspaper names."""
    if not isinstance(raw, str):
        return "Other"
    key = raw.strip().lower().replace(" ", "-").replace("_", "-")
    if "bola" in key:
        return "A Bola"
    if "record" in key:
        return "Record"
    if "jogo" in key:
        return "O Jogo"
    if "sapo" in key:
        return "SAPO"
    if "noticia" in key or "nam" in key or "minuto" in key:
        return "Notícias ao Minuto"
    if "zap" in key:
        return "ZAP"
    if "euronews" in key:
        return "Euronews"
    return "Other"


# ---------------------------------------------------------------------------
# Tab 1 — Longitudinal evolution
# ---------------------------------------------------------------------------

@st.cache_data(ttl=600, show_spinner=False)
def fetch_visual_yearly(filter_athletes: bool = False, filter_prominent: bool = False) -> pd.DataFrame:
    """
    Aggregates cover face detections by year, newspaper and gender.
    Returns: year | source | gender | count | avg_prominence | avg_confidence

    filter_athletes:  keep only faces annotated as 'athlete' (requires annotation tool).
                      Falls back to prominence proxy when annotation is not available.
    filter_prominent: keep only faces covering >= PROMINENCE_THRESHOLD % of the cover
                      (the woman is the main visual subject of the page).
    Both filters can be active simultaneously — they stack (AND logic).
    """
    db = get_db()

    pipeline = [{"$unwind": "$faces_detected"}]
    match = {}

    if filter_athletes:
        # Minimum coverage threshold applied to both genders.
        match["faces_detected.cover_coverage_percentage"] = {"$gte": 0.17}
        if person_type_annotated():
            # Female faces: only those annotated as 'athlete' pass (publicity/other/not_woman excluded).
            # Male faces: no person_type stored, so $nin treats the missing field as null
            # (not in the exclusion list) and they pass through — filtered by coverage only.
            match["faces_detected.person_type"] = {"$nin": ["publicity", "other", "not_woman"]}

    if filter_prominent:
        match["faces_detected.cover_coverage_percentage"] = {"$gte": PROMINENCE_THRESHOLD}

    if match:
        pipeline.append({"$match": match})
    pipeline += [
        {"$group": {
            "_id": {
                "year": "$year",
                "source": "$source",
                "gender": "$faces_detected.gender",
            },
            "count": {"$sum": 1},
            "avg_prominence": {"$avg": "$faces_detected.cover_coverage_percentage"},
            "avg_confidence": {"$avg": "$faces_detected.gender_confidence"},
        }},
        {"$sort": {"_id.year": 1}},
    ]

    rows = list(db["covers_analysis"].aggregate(pipeline, allowDiskUse=True))
    if not rows:
        return pd.DataFrame(columns=["year", "source", "gender", "count", "avg_prominence", "avg_confidence"])

    df = pd.json_normalize(rows)
    df.rename(columns={"_id.year": "year", "_id.source": "source", "_id.gender": "gender"}, inplace=True)
    df["source"] = df["source"].apply(_normalise_source)
    df["year"] = df["year"].astype(int)
    return df


# Filter applied to all text queries: require a non-empty body_text so that
# gender classification is based on full article content, not just the title.
_BODY_FILTER = {"body_text": {"$nin": [None, ""]}}


@st.cache_data(ttl=600, show_spinner=False)
def fetch_text_yearly(filter_body: bool = True) -> pd.DataFrame:
    """
    Aggregates article gender classifications by year and newspaper.
    filter_body=True (default): exclude articles without body_text.
    Returns: year | source | text_gender | count
    """
    db = get_db()
    pipeline = []
    if filter_body:
        pipeline.append({"$match": _BODY_FILTER})
    pipeline += [
        {"$project": {
            "year": 1,
            "journal": {"$ifNull": ["$journal", "$source"]},
            "verdict": {
                "$ifNull": [
                    "$gender_analysis.verdict",
                    "$gender_analysis.dominant_gender",
                    "Undetermined"
                ]
            }
        }},
        {"$group": {
            "_id": {"year": "$year", "journal": "$journal", "verdict": "$verdict"},
            "count": {"$sum": 1},
        }},
        {"$sort": {"_id.year": 1}},
    ]

    rows = list(db["articles_final"].aggregate(pipeline, allowDiskUse=True))
    if not rows:
        return pd.DataFrame(columns=["year", "source", "text_gender", "count"])

    df = pd.json_normalize(rows)
    df.rename(columns={"_id.year": "year", "_id.journal": "source", "_id.verdict": "text_gender"}, inplace=True)

    gender_map = {
        "Masculino": "Man", "Feminino": "Woman",
        "Indeterminado": "Undetermined", "Neutro/Equilibrado": "Undetermined",
    }
    df["text_gender"] = df["text_gender"].map(lambda x: gender_map.get(x, x))
    df["source"] = df["source"].apply(_normalise_source)
    df["year"] = df["year"].astype(int)
    return df


# ---------------------------------------------------------------------------
# Text quality
# ---------------------------------------------------------------------------

@st.cache_data(ttl=600, show_spinner=False)
def fetch_text_quality_by_year() -> pd.DataFrame:
    """
    Returns per-year body_text null rate for articles_final.
    Columns: year | total | null_body | null_pct
    Used to flag years where classification was based mostly on titles only.
    """
    db = get_db()
    pipeline = [
        {"$group": {
            "_id": "$year",
            "total":     {"$sum": 1},
            "null_body": {"$sum": {"$cond": [
                {"$or": [{"$eq": ["$body_text", None]}, {"$eq": ["$body_text", ""]}]},
                1, 0
            ]}},
        }},
        {"$sort": {"_id": 1}},
    ]
    rows = list(db["articles_final"].aggregate(pipeline, allowDiskUse=True))
    if not rows:
        return pd.DataFrame(columns=["year", "total", "null_body", "null_pct"])
    df = pd.json_normalize(rows).rename(columns={"_id": "year"})
    df["year"] = df["year"].astype(str).str.strip().astype(int)
    df["null_pct"] = (df["null_body"] / df["total"] * 100).round(1)
    return df


# ---------------------------------------------------------------------------
# Tab 2 — Visual prominence and cross-axis correlation
# ---------------------------------------------------------------------------

@st.cache_data(ttl=600, show_spinner=False)
def fetch_prominence_detail(filter_athletes: bool = False, filter_prominent: bool = False) -> pd.DataFrame:
    """Alias for fetch_visual_yearly, used explicitly in the prominence section."""
    return fetch_visual_yearly(filter_athletes=filter_athletes, filter_prominent=filter_prominent)


@st.cache_data(ttl=600, show_spinner=False)
def fetch_visual_text_correlation() -> pd.DataFrame:
    """
    Computes female representation percentage per year for both axes.
    Returns: year | visual_female_pct | text_female_pct
    """
    vis = fetch_visual_yearly()
    txt = fetch_text_yearly()

    if vis.empty or txt.empty:
        return pd.DataFrame()

    vis_piv = vis.groupby(["year", "gender"])["count"].sum().unstack(fill_value=0).reset_index()
    vis_piv["visual_female_pct"] = (
        vis_piv.get("Woman", 0) /
        (vis_piv.get("Woman", 0) + vis_piv.get("Man", 0)).replace(0, float("nan"))
    ) * 100

    txt_piv = txt.groupby(["year", "text_gender"])["count"].sum().unstack(fill_value=0).reset_index()
    txt_piv["text_female_pct"] = (
        txt_piv.get("Woman", 0) /
        (txt_piv.get("Woman", 0) + txt_piv.get("Man", 0)).replace(0, float("nan"))
    ) * 100

    merged = pd.merge(
        vis_piv[["year", "visual_female_pct"]],
        txt_piv[["year", "text_female_pct"]],
        on="year", how="inner"
    ).dropna()
    return merged


# ---------------------------------------------------------------------------
# Tab 3 — Diversity, sports and semantics
# ---------------------------------------------------------------------------

@st.cache_data(ttl=600, show_spinner=False)
def fetch_top_entities(top_n: int = 20) -> pd.DataFrame:
    """
    Returns the top N feminine NER entities ranked by mention count.
    Only articles with non-empty body_text are included.
    Returns: entity | count
    """
    db = get_db()
    pipeline = [
        {"$match": _BODY_FILTER},
        {"$project": {
            "year": 1,
            "source": {"$ifNull": ["$journal", "$source"]},
            "feminine_entities": "$gender_analysis.details.protagonists.feminine",
        }},
        {"$unwind": {"path": "$feminine_entities", "preserveNullAndEmptyArrays": False}},
        {"$group": {"_id": "$feminine_entities", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": top_n},
    ]
    rows = list(db["articles_final"].aggregate(pipeline, allowDiskUse=True))
    if not rows:
        return pd.DataFrame(columns=["entity", "count"])
    df = pd.json_normalize(rows)
    df.rename(columns={"_id": "entity"}, inplace=True)
    return df


# Keywords per sport modality for text-based detection (used when the 'sport' field is absent)
SPORT_KEYWORDS: dict[str, list[str]] = {
    "Futebol":      ["futebol", "golo", "golos", "bola", "defesa", "avançada",
                     "atacante", "liga", "campeonato", "seleção", "penalty", "árbitro",
                     "baliza", "guarda-redes", "fifa", "uefa", "premier league", "la liga"],
    "Atletismo":    ["atletismo", "maratona", "corrida", "velocidade", "salto",
                     "lançamento", "sprint", "pista", "disco", "martelo", "peso",
                     "decatlo", "heptatlo", "estafeta", "obstáculos"],
    "Ténis":        ["ténis", "tennis", "grand slam", "wimbledon", "roland garros",
                     "us open", "australian open", "set", "match", "ace", "serviço",
                     "wta", "atp", "itf", "courts", "torneio de ténis"],
    "Natação":      ["natação", "nadadora", "piscina", "metros livres",
                     "bruços", "costas", "borboleta", "mariposa", "fina",
                     "piscina olímpica", "nado sincronizado", "polo aquático"],
    "Ginástica":    ["ginástica", "ginasta", "rítmica", "artística", "trampolim",
                     "trave", "paralelas", "barra fixa", "solo", "aparelho",
                     "biles", "simone biles", "fig", "fig gymnastics",
                     "pirueta", "salto mortal", "gym", "acrobacia"],
    "Surf":         ["surf", "surfista", "onda", "meo rip curl", "wsl", "ondas",
                     "bodyboard", "prancha", "pipeline", "nazaré"],
    "Basquetebol":  ["basquetebol", "basquete", "nba", "cesto", "triplo duplo",
                     "wnba", "euroliga", "three-pointer", "playoff"],
    "Voleibol":     ["voleibol", "volei", "vôlei", "rede", "bloco", "receção",
                     "voleibol de praia", "beach volley"],
    "Ciclismo":     ["ciclismo", "ciclista", "volta a", "pedalada", "etapa",
                     "tour de france", "giro", "vuelta", "pelotão", "crono"],
    "Andebol":      ["andebol", "handball", "sete metros", "guarda-redes andebol"],
    "Judo":         ["judo", "judoca", "tatami", "ippon", "waza", "kata", "dan"],
    "Boxe":         ["boxe", "boxeo", "pugilismo", "nocaute", "round", "combate",
                     "peso pena", "peso leve", "peso médio", "campeã mundial"],
    "Triatlo":      ["triatlo", "triatleta", "ironman", "duatlo"],
    "Golfe":        ["golfe", "golfista", "ryder cup", "masters", "green", "par",
                     "birdie", "eagle", "pgr", "lpga"],
    "Remo":         ["remo", "remadora", "canoagem", "caiaque", "kayak",
                     "barco", "world rowing"],
    "Hóquei":       ["hóquei", "hoquei", "hockey", "stick", "campo de hóquei"],
    "Esgrima":      ["esgrima", "esgrimista", "florete", "sabre", "espada"],
    "Tiro":         ["tiro desportivo", "tiro ao alvo", "carabina", "pistola desportiva"],
    "Luta":         ["luta olímpica", "wrestling", "greco-romana", "freestyle wrestling"],
    "Pentatlo":     ["pentatlo", "pentatlo moderno"],
}


@st.cache_data(ttl=600, show_spinner=False)
def fetch_sports_by_keywords() -> pd.DataFrame:
    """
    Detects sport modality in female-tagged articles using keyword matching.
    Fallback for when the structured 'sport' field is absent.
    Each sport is queried separately with a regex $match so no Python-side limit is needed.
    Returns: sport | count
    """
    db = get_db()
    rows = []
    for sport, keywords in SPORT_KEYWORDS.items():
        regex_pattern = "|".join(keywords)
        pipeline = [
            {"$match": {"$and": [
                {"$or": [
                    {"gender_analysis.verdict": "Feminino"},
                    {"gender_analysis.dominant_gender": "Feminino"},
                ]},
                {"$or": [
                    {"title":     {"$regex": regex_pattern, "$options": "i"}},
                    {"body_text": {"$regex": regex_pattern, "$options": "i"}},
                ]},
            ]}},
            {"$count": "count"},
        ]
        result = list(db["articles_final"].aggregate(pipeline, allowDiskUse=True))
        if result:
            rows.append({"sport": sport, "count": result[0]["count"]})

    if not rows:
        return pd.DataFrame(columns=["sport", "count"])
    return pd.DataFrame(rows).sort_values("count", ascending=False)


@st.cache_data(ttl=600, show_spinner=False)
def fetch_sports_by_year() -> pd.DataFrame:
    """
    Same keyword detection as fetch_sports_by_keywords but broken down by year.
    Used for the sport × year heatmap.
    Each sport is queried separately with a regex $match so no Python-side limit is needed.
    Returns: sport | year | count
    """
    db = get_db()
    rows = []
    for sport, keywords in SPORT_KEYWORDS.items():
        regex_pattern = "|".join(keywords)
        pipeline = [
            {"$match": {"$and": [
                {"$or": [
                    {"gender_analysis.verdict": "Feminino"},
                    {"gender_analysis.dominant_gender": "Feminino"},
                ]},
                {"$or": [
                    {"title":     {"$regex": regex_pattern, "$options": "i"}},
                    {"body_text": {"$regex": regex_pattern, "$options": "i"}},
                ]},
            ]}},
            {"$group": {"_id": "$year", "count": {"$sum": 1}}},
            {"$sort": {"_id": 1}},
        ]
        for doc in db["articles_final"].aggregate(pipeline, allowDiskUse=True):
            if doc["_id"] is not None:
                rows.append({"sport": sport, "year": int(doc["_id"]), "count": doc["count"]})

    if not rows:
        return pd.DataFrame(columns=["sport", "year", "count"])
    return pd.DataFrame(rows)


@st.cache_data(ttl=600, show_spinner=False)
def fetch_sports_breakdown() -> pd.DataFrame:
    """
    Returns sport coverage counts for female-tagged articles.
    Uses the structured 'sport' field if present; falls back to keyword detection.
    Returns: sport | count
    """
    db = get_db()
    pipeline = [
        {"$match": {
            "$or": [
                {"gender_analysis.verdict": "Feminino"},
                {"gender_analysis.dominant_gender": "Feminino"},
            ]
        }},
        {"$group": {
            "_id": {"$ifNull": ["$sport", "$category", "$modalidade", None]},
            "count": {"$sum": 1}
        }},
        {"$match": {"_id": {"$ne": None}}},
        {"$sort": {"count": -1}},
        {"$limit": 15},
    ]
    rows = list(db["articles_final"].aggregate(pipeline, allowDiskUse=True))
    if not rows:
        return fetch_sports_by_keywords()
    df = pd.json_normalize(rows)
    df.rename(columns={"_id": "sport"}, inplace=True)
    return df


@st.cache_data(ttl=600, show_spinner=False)
def fetch_entity_distribution(gender_key: str = "feminine") -> pd.DataFrame:
    """
    Returns all NER entities with their total mention count for HHI/diversity analysis.
    gender_key: 'feminine' or 'masculine'
    Returns: entity | count
    """
    db = get_db()
    pipeline = [
        {"$unwind": {
            "path": f"$gender_analysis.details.protagonists.{gender_key}",
            "preserveNullAndEmptyArrays": False,
        }},
        {"$group": {
            "_id": f"$gender_analysis.details.protagonists.{gender_key}",
            "count": {"$sum": 1},
        }},
        {"$sort": {"count": -1}},
    ]
    rows = list(db["articles_final"].aggregate(pipeline, allowDiskUse=True))
    if not rows:
        return pd.DataFrame(columns=["entity", "count"])
    df = pd.json_normalize(rows)
    df.rename(columns={"_id": "entity"}, inplace=True)
    return df


@st.cache_data(ttl=600, show_spinner=False)
def fetch_semantic_keywords(top_n: int = 40) -> pd.DataFrame:
    """
    Fetches text from female-tagged articles for YAKE! keyword extraction.
    Capped at 500 documents to keep extraction fast.
    Only articles with non-empty body_text are included.
    Returns: DataFrame with a single 'text' column.
    """
    db = get_db()
    pipeline = [
        {"$match": {
            **_BODY_FILTER,
            "$or": [
                {"gender_analysis.verdict": "Feminino"},
                {"gender_analysis.dominant_gender": "Feminino"},
            ]
        }},
        {"$project": {
            "text": {"$concat": [
                {"$ifNull": ["$title", ""]}, ". ",
                {"$ifNull": ["$body_text", ""]}
            ]}
        }},
        {"$limit": 500},
    ]
    rows = list(db["articles_final"].aggregate(pipeline, allowDiskUse=True))
    if not rows:
        return pd.DataFrame(columns=["text"])
    return pd.DataFrame([r.get("text", "") for r in rows], columns=["text"])


# ---------------------------------------------------------------------------
# Pipeline statistics (shared with evaluation/pipeline_evaluation.py)
# ---------------------------------------------------------------------------

@st.cache_data(ttl=600, show_spinner=False)
def fetch_pipeline_stats() -> dict:
    """Returns a summary dict of processing volumes, confidence rates and NER counts."""
    db = get_db()

    total_raw = db["articles_final"].count_documents({})
    total_classified = db["articles_final"].count_documents({
        "$or": [
            {"gender_analysis.verdict": {"$exists": True, "$ne": None}},
            {"gender_analysis.dominant_gender": {"$exists": True, "$ne": None}},
        ]
    })

    conf_pipeline = [
        {"$unwind": "$faces_detected"},
        {"$group": {
            "_id": None,
            "high_conf": {"$sum": {"$cond": [{"$gte": ["$faces_detected.gender_confidence", 0.90]}, 1, 0]}},
            "low_conf":  {"$sum": {"$cond": [{"$lt":  ["$faces_detected.gender_confidence", 0.90]}, 1, 0]}},
            "total_faces": {"$sum": 1},
        }}
    ]
    conf_result = list(db["covers_analysis"].aggregate(conf_pipeline))
    conf = conf_result[0] if conf_result else {"high_conf": 0, "low_conf": 0, "total_faces": 0}

    ner_pipeline = [
        {"$unwind": {"path": "$gender_analysis.details.protagonists.feminine", "preserveNullAndEmptyArrays": False}},
        {"$group": {"_id": "$gender_analysis.details.protagonists.feminine"}},
        {"$count": "unique_feminine"},
    ]
    ner_result = list(db["articles_final"].aggregate(ner_pipeline))
    unique_feminine = ner_result[0]["unique_feminine"] if ner_result else 0

    ner_pipeline_m = [
        {"$unwind": {"path": "$gender_analysis.details.protagonists.masculine", "preserveNullAndEmptyArrays": False}},
        {"$group": {"_id": "$gender_analysis.details.protagonists.masculine"}},
        {"$count": "unique_masculine"},
    ]
    ner_result_m = list(db["articles_final"].aggregate(ner_pipeline_m))
    unique_masculine = ner_result_m[0]["unique_masculine"] if ner_result_m else 0

    total_covers = db["covers_analysis"].count_documents({})

    return {
        "total_raw_articles": total_raw,
        "total_classified_articles": total_classified,
        "classification_rate_pct": round(total_classified / total_raw * 100, 2) if total_raw else 0,
        "total_covers_processed": total_covers,
        "total_faces_detected": conf.get("total_faces", 0),
        "faces_high_confidence": conf.get("high_conf", 0),
        "faces_low_confidence": conf.get("low_conf", 0),
        "high_conf_rate_pct": round(conf.get("high_conf", 0) / conf.get("total_faces", 1) * 100, 2),
        "unique_feminine_entities": unique_feminine,
        "unique_masculine_entities": unique_masculine,
    }


# ---------------------------------------------------------------------------
# Athlete detail queries (Q8 / Q9C)
# ---------------------------------------------------------------------------

@st.cache_data(ttl=600, show_spinner=False)
def fetch_athlete_articles(entity_name: str, gender_key: str = "feminine") -> pd.DataFrame:
    """
    Returns all articles that mention a specific named entity.
    Columns: year | source | content
    """
    db = get_db()
    field = f"gender_analysis.details.protagonists.{gender_key}"
    pipeline = [
        {"$match": {field: entity_name}},
        {"$project": {
            "year": 1,
            "source": {"$ifNull": ["$journal", "$source"]},
            "title": 1,
            "body_text": 1,
        }},
        {"$limit": 500},
    ]
    rows = list(db["articles_final"].aggregate(pipeline))
    if not rows:
        return pd.DataFrame(columns=["year", "source", "content"])
    records = [
        {
            "year":    r.get("year"),
            "source":  _normalise_source(str(r.get("source", ""))),
            "content": f"{r.get('title', '')}. {r.get('body_text', '')}",
        }
        for r in rows
    ]
    return pd.DataFrame(records)


@st.cache_data(ttl=600, show_spinner=False)
def person_type_annotated() -> bool:
    """Returns True if at least one female face has been manually annotated with person_type."""
    db = get_db()
    doc = db["covers_analysis"].find_one(
        {"faces_detected": {"$elemMatch": {"gender": "Woman", "person_type": {"$exists": True, "$ne": None}}}},
        {"_id": 1},
    )
    return doc is not None


@st.cache_data(ttl=600, show_spinner=False)
def fetch_female_classification_breakdown() -> dict:
    """
    Returns a detailed breakdown of all originally-detected female faces:
      - per person_type label (athlete, publicity, other, not_woman)
      - how many occupy >= 0.17% of the cover
    """
    db = get_db()
    pipeline = [
        {"$unwind": "$faces_detected"},
        {"$match": {"$or": [
            {"faces_detected.gender": "Woman"},
            {"faces_detected.gender_corrected": "Woman"},
        ]}},
        {"$group": {
            "_id": "$faces_detected.person_type",
            "count": {"$sum": 1},
            "above_threshold": {"$sum": {"$cond": [
                {"$gte": ["$faces_detected.cover_coverage_percentage", 0.17]}, 1, 0
            ]}},
        }},
    ]
    rows = list(db["covers_analysis"].aggregate(pipeline))
    result = {}
    for r in rows:
        result[r["_id"] or "unannotated"] = {
            "count": r["count"],
            "above_threshold": r["above_threshold"],
        }
    return result


@st.cache_data(ttl=600, show_spinner=False)
def fetch_visual_fp_comparison() -> pd.DataFrame:
    """
    Returns female face counts per year broken down into three categories:
      - count_athlete:     person_type = 'athlete'  (or prominence proxy when not annotated)
      - count_non_sport:   person_type in ['publicity', 'other', 'not_woman']
      - count_unannotated: no person_type yet (only present during partial annotation)
    Columns: year | count_athlete | count_non_sport | count_unannotated | annotated
    """
    db = get_db()
    use_annotation = person_type_annotated()

    def _count_by_year(match_extra):
        pipeline = [
            {"$unwind": "$faces_detected"},
            {"$match": {**{"faces_detected.gender": "Woman"}, **match_extra}},
            {"$group": {"_id": "$year", "count": {"$sum": 1}}},
            {"$sort": {"_id": 1}},
        ]
        return {r["_id"]: r["count"]
                for r in db["covers_analysis"].aggregate(pipeline)}

    if use_annotation:
        athlete_counts     = _count_by_year({"faces_detected.person_type": {"$in": ["athlete", "atleta"]}})
        non_sport_counts   = _count_by_year({"faces_detected.person_type": {"$in": ["publicity", "other", "not_woman"]}})
        unannotated_counts = _count_by_year({"faces_detected.person_type": {"$exists": False}})
        none_counts        = _count_by_year({"faces_detected.person_type": None})
        for y, v in none_counts.items():
            unannotated_counts[y] = unannotated_counts.get(y, 0) + v
    else:
        athlete_counts     = _count_by_year({"faces_detected.cover_coverage_percentage": {"$gte": PROMINENCE_THRESHOLD}})
        non_sport_counts   = _count_by_year({"faces_detected.cover_coverage_percentage": {"$lt": PROMINENCE_THRESHOLD}})
        unannotated_counts = {}

    years = sorted(set(athlete_counts) | set(non_sport_counts) | set(unannotated_counts))
    if not years:
        return pd.DataFrame(columns=["year", "count_athlete", "count_non_sport", "count_unannotated", "annotated"])

    return pd.DataFrame({
        "year":               years,
        "count_athlete":      [athlete_counts.get(y, 0)     for y in years],
        "count_non_sport":    [non_sport_counts.get(y, 0)   for y in years],
        "count_unannotated":  [unannotated_counts.get(y, 0) for y in years],
        "annotated":          use_annotation,
    })
