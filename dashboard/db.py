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


@st.cache_data(ttl=600, show_spinner=False)
def fp_field_exists() -> bool:
    """Returns True if at least one face document has 'person_type' populated."""
    db = get_db()
    doc = db["covers_analysis"].find_one(
        {"faces_detected.person_type": {"$exists": True, "$ne": None}},
        {"_id": 1},
    )
    return doc is not None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_NEWSPAPER_MAP = {
    "a-bola": "A Bola", "abola": "A Bola",
    "record": "Record",
    "o-jogo": "O Jogo", "ojogo": "O Jogo",
}

def _normalise_source(raw: str) -> str:
    """Normalise raw source strings to display newspaper names."""
    if not isinstance(raw, str):
        return "Other"
    key = raw.strip().lower().replace(" ", "-")
    if "bola" in key:
        return "A Bola"
    if "record" in key:
        return "Record"
    if "jogo" in key:
        return "O Jogo"
    return "Other"


# ---------------------------------------------------------------------------
# Tab 1 — Longitudinal evolution
# ---------------------------------------------------------------------------

@st.cache_data(ttl=600, show_spinner=False)
def fetch_visual_yearly(filter_fp: bool = False) -> pd.DataFrame:
    """
    Aggregates cover face detections by year, newspaper and gender.
    Returns: year | source | gender | count | avg_prominence | avg_confidence
    filter_fp: restrict to person_type='athlete' only if the field exists in the DB.
    """
    db = get_db()

    # Only apply the false-positive filter when the field is actually present
    apply_fp = filter_fp and fp_field_exists()

    pipeline = [{"$unwind": "$faces_detected"}]
    if apply_fp:
        pipeline.append({"$match": {"faces_detected.person_type": {"$in": ["athlete", "atleta"]}}})
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


@st.cache_data(ttl=600, show_spinner=False)
def fetch_text_yearly() -> pd.DataFrame:
    """
    Aggregates article gender classifications by year and newspaper.
    Returns: year | source | text_gender | count
    """
    db = get_db()
    pipeline = [
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
    return df[df["source"].isin(["A Bola", "Record", "O Jogo"])]


# ---------------------------------------------------------------------------
# Tab 2 — Visual prominence and cross-axis correlation
# ---------------------------------------------------------------------------

@st.cache_data(ttl=600, show_spinner=False)
def fetch_prominence_detail(filter_fp: bool = False) -> pd.DataFrame:
    """Alias for fetch_visual_yearly, used explicitly in the prominence section."""
    return fetch_visual_yearly(filter_fp=filter_fp)


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
    Returns: entity | count
    """
    db = get_db()
    pipeline = [
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
                     "atacante", "liga", "campeonato", "seleção"],
    "Atletismo":    ["atletismo", "maratona", "corrida", "velocidade", "salto",
                     "lançamento", "sprint", "pista"],
    "Ténis":        ["ténis", "tennis", "grand slam", "wimbledon", "roland garros",
                     "us open", "australian open", "set", "match"],
    "Natação":      ["natação", "nadadora", "piscina", "metros livres",
                     "braco", "bruços", "costas", "borboleta"],
    "Ginástica":    ["ginástica", "ginasta", "rítmica", "artística", "trampolim"],
    "Surf":         ["surf", "surfista", "onda", "meo rip curl", "wsl", "ondas"],
    "Basquetebol":  ["basquetebol", "basquete", "nba", "cesto", "triplo duplo"],
    "Voleibol":     ["voleibol", "volei", "vôlei", "rede"],
    "Ciclismo":     ["ciclismo", "ciclista", "volta a", "pedalada", "etapa"],
    "Andebol":      ["andebol", "handball"],
    "Judo":         ["judo", "judoca", "tatami", "ippon"],
    "Boxe":         ["boxe", "boxeo", "pugilismo", "nocaute"],
    "Triatlo":      ["triatlo", "triatleta", "ironman"],
    "Golfe":        ["golfe", "golfista", "ryder cup", "masters"],
    "Remo":         ["remo", "remadora", "canoagem", "caiaque"],
}


@st.cache_data(ttl=600, show_spinner=False)
def fetch_sports_by_keywords() -> pd.DataFrame:
    """
    Detects sport modality in female-tagged articles using keyword matching.
    Fallback for when the structured 'sport' field is absent.
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
        {"$project": {
            "year": 1,
            "text": {"$concat": [
                {"$toLower": {"$ifNull": ["$title", ""]}}, " ",
                {"$toLower": {"$ifNull": ["$body_text", ""]}}
            ]},
        }},
        {"$limit": 2000},
    ]
    docs = list(db["articles_final"].aggregate(pipeline, allowDiskUse=True))
    if not docs:
        return pd.DataFrame(columns=["sport", "count"])

    rows = []
    for doc in docs:
        text = doc.get("text", "")
        year = doc.get("year")
        for sport, keywords in SPORT_KEYWORDS.items():
            if any(kw in text for kw in keywords):
                rows.append({"sport": sport, "year": year})

    if not rows:
        return pd.DataFrame(columns=["sport", "count"])

    df = pd.DataFrame(rows)
    return df.groupby("sport").size().reset_index(name="count").sort_values("count", ascending=False)


@st.cache_data(ttl=600, show_spinner=False)
def fetch_sports_by_year() -> pd.DataFrame:
    """
    Same keyword detection as fetch_sports_by_keywords but broken down by year.
    Used for the sport × year heatmap.
    Returns: sport | year | count
    """
    db = get_db()
    pipeline = [
        {"$match": {
            "$or": [
                {"gender_analysis.verdict": "Feminino"},
                {"gender_analysis.dominant_gender": "Feminino"},
            ]
        }},
        {"$project": {
            "year": 1,
            "text": {"$concat": [
                {"$toLower": {"$ifNull": ["$title", ""]}}, " ",
                {"$toLower": {"$ifNull": ["$body_text", ""]}}
            ]},
        }},
        {"$limit": 2000},
    ]
    docs = list(db["articles_final"].aggregate(pipeline, allowDiskUse=True))
    if not docs:
        return pd.DataFrame(columns=["sport", "year", "count"])

    rows = []
    for doc in docs:
        text = doc.get("text", "")
        year = doc.get("year")
        for sport, keywords in SPORT_KEYWORDS.items():
            if any(kw in text for kw in keywords):
                rows.append({"sport": sport, "year": year})

    if not rows:
        return pd.DataFrame(columns=["sport", "year", "count"])

    df = pd.DataFrame(rows)
    return df.groupby(["sport", "year"]).size().reset_index(name="count")


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
    Returns: DataFrame with a single 'text' column.
    """
    db = get_db()
    pipeline = [
        {"$match": {
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
