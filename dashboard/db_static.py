"""
GEMA — static data layer for HuggingFace Space.
Reads pre-exported Parquet/JSON files instead of MongoDB.
"""
import json, os
import pandas as pd
import streamlit as st

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

PROMINENCE_THRESHOLD = 0.17


def _p(name: str) -> str:
    return os.path.join(DATA_DIR, name)


def _normalise_source(raw: str) -> str:
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


@st.cache_data(show_spinner=False)
def fetch_visual_yearly(filter_athletes: bool = False, filter_prominent: bool = False) -> pd.DataFrame:
    df = pd.read_parquet(_p("visual_yearly.parquet"))
    df["source"] = df["source"].apply(_normalise_source)
    df["year"] = df["year"].astype(int)
    if filter_prominent:
        df = df[df["avg_prominence"] >= PROMINENCE_THRESHOLD]
    return df


@st.cache_data(show_spinner=False)
def fetch_text_yearly(filter_body: bool = True) -> pd.DataFrame:
    df = pd.read_parquet(_p("text_yearly.parquet"))
    gender_map = {
        "Masculino": "Man", "Feminino": "Woman",
        "Indeterminado": "Undetermined", "Neutro/Equilibrado": "Undetermined",
    }
    df["text_gender"] = df["text_gender"].map(lambda x: gender_map.get(x, x))
    df["source"] = df["source"].apply(_normalise_source)
    df["year"] = df["year"].astype(int)
    totals = df.groupby(["year", "source"])["count"].sum()
    valid = totals[totals >= 10].index
    df = df.set_index(["year", "source"])
    df = df[df.index.isin(valid)].reset_index()
    return df


@st.cache_data(show_spinner=False)
def fetch_text_quality_by_year() -> pd.DataFrame:
    df = pd.read_parquet(_p("text_quality.parquet"))
    df["year"] = df["year"].astype(str).str.strip().astype(int)
    df["null_pct"] = (df["null_body"] / df["total"] * 100).round(1)
    return df


@st.cache_data(show_spinner=False)
def fetch_prominence_detail(filter_athletes: bool = False, filter_prominent: bool = False) -> pd.DataFrame:
    return fetch_visual_yearly(filter_athletes=filter_athletes, filter_prominent=filter_prominent)


@st.cache_data(show_spinner=False)
def fetch_visual_text_correlation() -> pd.DataFrame:
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
    return pd.merge(
        vis_piv[["year", "visual_female_pct"]],
        txt_piv[["year", "text_female_pct"]],
        on="year", how="inner"
    ).dropna()


@st.cache_data(show_spinner=False)
def fetch_top_entities(top_n: int = 20) -> pd.DataFrame:
    df = pd.read_parquet(_p("top_entities.parquet"))
    return df.head(top_n)


@st.cache_data(show_spinner=False)
def fetch_sports_by_keywords() -> pd.DataFrame:
    return pd.read_parquet(_p("sports_by_keywords.parquet")).sort_values("count", ascending=False)


@st.cache_data(show_spinner=False)
def fetch_sports_by_year() -> pd.DataFrame:
    return pd.read_parquet(_p("sports_by_year.parquet"))


@st.cache_data(show_spinner=False)
def fetch_sports_breakdown() -> pd.DataFrame:
    return fetch_sports_by_keywords()


@st.cache_data(show_spinner=False)
def fetch_entity_distribution(gender_key: str = "feminine") -> pd.DataFrame:
    fname = "entity_dist_feminine.parquet" if gender_key == "feminine" else "entity_dist_masculine.parquet"
    return pd.read_parquet(_p(fname))


@st.cache_data(show_spinner=False)
def fetch_semantic_keywords(top_n: int = 40) -> pd.DataFrame:
    return pd.read_parquet(_p("semantic_texts.parquet"))


@st.cache_data(show_spinner=False)
def fetch_pipeline_stats() -> dict:
    with open(_p("pipeline_stats.json")) as f:
        return json.load(f)


@st.cache_data(show_spinner=False)
def fetch_athlete_articles(entity_name: str, gender_key: str = "feminine") -> pd.DataFrame:
    df = pd.read_parquet(_p("athlete_articles.parquet"))
    df = df[(df["entity"] == entity_name) & (df["gender_key"] == gender_key)].copy()
    df["source"] = df["source"].apply(_normalise_source)
    df["content"] = df["title"].fillna("") + ". " + df["body_text"].fillna("")
    return df[["year", "source", "content"]].head(500)


def person_type_annotated() -> bool:
    return False


@st.cache_data(show_spinner=False)
def fetch_female_classification_breakdown() -> dict:
    return {}


@st.cache_data(show_spinner=False)
def fetch_visual_fp_comparison() -> pd.DataFrame:
    df = fetch_visual_yearly()
    woman = df[df["gender"] == "Woman"].copy()
    years = sorted(woman["year"].unique())
    athlete_counts = {}
    non_sport_counts = {}
    for _, row in woman.iterrows():
        y = row["year"]
        if row.get("avg_prominence", 0) >= PROMINENCE_THRESHOLD:
            athlete_counts[y] = athlete_counts.get(y, 0) + row["count"]
        else:
            non_sport_counts[y] = non_sport_counts.get(y, 0) + row["count"]
    return pd.DataFrame({
        "year": years,
        "count_athlete": [athlete_counts.get(y, 0) for y in years],
        "count_non_sport": [non_sport_counts.get(y, 0) for y in years],
        "count_unannotated": [0] * len(years),
        "annotated": False,
    })
