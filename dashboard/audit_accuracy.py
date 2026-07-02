"""
GEMA — Gender Accuracy Audit
Randomly samples 20 covers per newspaper and lets you verify
pipeline gender predictions face by face, then exports to CSV.

Run: streamlit run dashboard/audit_accuracy.py
"""

import os
import random
import pandas as pd
import streamlit as st
from pymongo import MongoClient
from PIL import Image, ImageDraw

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

MONGO_URI = os.environ.get("MONGO_URI", "mongodb://172.17.16.1:27017/")
DB_NAME   = "estagio_desporto"

NEWSPAPERS = ["a-bola", "o-jogo", "record"]
NEWSPAPER_LABELS = {"a-bola": "A Bola", "o-jogo": "O Jogo", "record": "Record"}
N_COVERS    = 20
MIN_FACES   = 2  # only include covers with at least this many detected faces

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
IMG_DIR      = os.path.join(PROJECT_ROOT, "data", "capas", "images")

GENDER_PT = {"Man": "Homem", "Woman": "Mulher"}  # pipeline → Portuguese label

st.set_page_config(
    page_title="GEMA · Accuracy Audit",
    page_icon="🔍",
    layout="wide",
)

# ---------------------------------------------------------------------------
# DB + data loading
# ---------------------------------------------------------------------------

@st.cache_resource
def get_db():
    return MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)[DB_NAME]


@st.cache_data
def load_sample(seed: int):
    """Load 20 random covers per newspaper with at least MIN_FACES detected faces."""
    db = get_db()
    sample = {}
    rng = random.Random(seed)
    for newspaper in NEWSPAPERS:
        covers = list(db["covers_analysis"].find(
            {"source": newspaper, "faces_detected": {"$exists": True, "$ne": []}},
            {"source": 1, "date": 1, "faces_detected": 1}
        ))
        # prefer covers with multiple faces
        multi = [c for c in covers if len(c["faces_detected"]) >= MIN_FACES]
        pool  = multi if len(multi) >= N_COVERS else covers
        selected = rng.sample(pool, min(N_COVERS, len(pool)))
        selected.sort(key=lambda c: str(c["date"]))
        sample[newspaper] = selected
    return sample


def _img_path(source: str, date) -> str:
    return os.path.join(IMG_DIR, f"{source}_{str(date)[:10]}.jpg")


def _face_key(cover_id, face_idx: int) -> str:
    return f"{cover_id}_{face_idx}"


def _pipeline_gender(face: dict) -> str:
    """Return the original pipeline gender before any manual correction.
    gender_corrected stores the pre-correction value; if absent, gender was never changed."""
    return face.get("gender_corrected") or face.get("gender", "?")


# ---------------------------------------------------------------------------
# Drawing
# ---------------------------------------------------------------------------

GENDER_COLORS    = {"Man": "#1f77b4", "Woman": "#e377c2"}
GENDER_COLORS_RGB = {"Man": (31, 119, 180), "Woman": (227, 119, 194)}

def _draw_faces(path: str, faces: list) -> Image.Image:
    img  = Image.open(path).convert("RGB")
    draw = ImageDraw.Draw(img)
    w, h = img.size

    for i, face in enumerate(faces):
        x1, y1, x2, y2 = face["bbox"]
        gender    = _pipeline_gender(face)
        color     = GENDER_COLORS.get(gender, "#aaaaaa")
        color_rgb = GENDER_COLORS_RGB.get(gender, (170, 170, 170))
        label     = f" #{i + 1} {GENDER_PT.get(gender, gender)} "

        # bounding box
        draw.rectangle([x1, y1, x2, y2], outline=color, width=4)

        # label background — solid filled rectangle above the box
        font_h = 18
        pad    = 2
        lx     = x1
        ly     = max(0, y1 - font_h - pad * 2)
        # estimate text width (≈9px per char at default font)
        tw     = len(label) * 9
        draw.rectangle([lx, ly, lx + tw, ly + font_h + pad * 2],
                       fill=color_rgb + (220,) if img.mode == "RGBA" else color_rgb)
        draw.text((lx + pad, ly + pad), label, fill="white")

    return img


def _crop_face(path: str, face: dict, padding: int = 20) -> Image.Image:
    """Return a small cropped thumbnail of a single face with padding."""
    img = Image.open(path).convert("RGB")
    w, h = img.size
    x1, y1, x2, y2 = face["bbox"]
    x1 = max(0, x1 - padding)
    y1 = max(0, y1 - padding)
    x2 = min(w, x2 + padding)
    y2 = min(h, y2 + padding)
    return img.crop((x1, y1, x2, y2))


# ---------------------------------------------------------------------------
# CSV export
# ---------------------------------------------------------------------------

def _build_dataframe(sample: dict, annotations: dict) -> pd.DataFrame:
    rows = []
    for newspaper in NEWSPAPERS:
        label  = NEWSPAPER_LABELS[newspaper]
        covers = sample[newspaper]
        for n, cover in enumerate(covers, 1):
            capa_name = f"{label} - Capa {n}"
            for i, face in enumerate(cover["faces_detected"]):
                pipeline_pt  = GENDER_PT.get(_pipeline_gender(face), "?")
                key          = _face_key(cover["_id"], i)
                correct      = annotations.get(key, "")
                if not correct:
                    match = ""
                elif correct == "Não é uma pessoa":
                    match = "FALSE DETECTION"
                else:
                    match = "TRUE" if correct == pipeline_pt else "FALSE"
                rows.append({
                    "Capa":                    capa_name,
                    "Jornal":                  label,
                    "Face Correta":            correct,
                    "Face Prevista (Pipeline)": pipeline_pt,
                    "Match":                   match,
                })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Session state init
# ---------------------------------------------------------------------------

if "annotations" not in st.session_state:
    st.session_state["annotations"] = {}

if "current_newspaper" not in st.session_state:
    st.session_state["current_newspaper"] = NEWSPAPERS[0]

if "current_cover_idx" not in st.session_state:
    st.session_state["current_cover_idx"] = 0

# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------

st.title("🔍 GEMA — Gender Accuracy Audit")
st.caption("Verify pipeline gender predictions on a random sample of 20 covers per newspaper.")

annotations: dict = st.session_state["annotations"]

# ---------------------------------------------------------------------------
# Sidebar — seed first, then load sample, then rest of navigation
# ---------------------------------------------------------------------------

seed = st.sidebar.number_input(
    "Random seed (change to get a different sample)",
    min_value=1, max_value=9999, value=99, step=1,
)
if seed != st.session_state.get("_last_seed"):
    st.session_state["annotations"] = {}
    st.session_state["current_cover_idx"] = 0
    st.session_state["_last_seed"] = seed
    annotations = st.session_state["annotations"]

sample = load_sample(seed)

with st.sidebar:
    st.divider()

    newspaper = st.selectbox(
        "Newspaper",
        NEWSPAPERS,
        format_func=lambda x: NEWSPAPER_LABELS[x],
        key="current_newspaper",
    )

    covers = sample[newspaper]
    total_faces = sum(len(c["faces_detected"]) for c in covers)
    annotated_faces = sum(
        1 for c in covers for i in range(len(c["faces_detected"]))
        if _face_key(c["_id"], i) in annotations
    )
    st.progress(annotated_faces / total_faces if total_faces else 0,
                text=f"{annotated_faces} / {total_faces} faces labelled")

    st.divider()

    # Cover selector
    cover_options = [f"Capa {i + 1} — {str(c['date'])[:10]}" for i, c in enumerate(covers)]
    selected_cover_label = st.radio("Select cover", cover_options,
                                    index=st.session_state["current_cover_idx"])
    cover_idx = cover_options.index(selected_cover_label)
    st.session_state["current_cover_idx"] = cover_idx

    st.divider()

    # Global progress across all newspapers
    st.markdown("**Overall progress**")
    all_total = sum(len(c["faces_detected"]) for covers in sample.values() for c in covers)
    all_done  = len(annotations)
    st.progress(all_done / all_total if all_total else 0,
                text=f"{all_done} / {all_total} total faces")

# ---------------------------------------------------------------------------
# Main area — current cover
# ---------------------------------------------------------------------------

cover     = covers[cover_idx]
path      = _img_path(cover["source"], cover["date"])
faces     = cover["faces_detected"]
label_str = NEWSPAPER_LABELS[newspaper]
capa_name = f"{label_str} - Capa {cover_idx + 1}"

st.subheader(f"{capa_name} · {str(cover['date'])[:10]}")

col_img, col_faces = st.columns([3, 2])

with col_img:
    if os.path.exists(path):
        img = _draw_faces(path, faces)
        st.image(img, use_container_width=True,
                 caption=f"Blue = pipeline says Man · Pink = pipeline says Woman")
    else:
        st.warning(f"Image not found: {path}")

with col_faces:
    st.markdown(f"**{len(faces)} face(s) detected on this cover**")
    st.caption("For each face, select what you see in the image.")
    st.divider()

    img_exists = os.path.exists(path)

    for i, face in enumerate(faces):
        pipeline_en = _pipeline_gender(face)
        pipeline_pt = GENDER_PT.get(pipeline_en, pipeline_en)
        key         = _face_key(cover["_id"], i)
        current_val = annotations.get(key)

        thumb_col, label_col = st.columns([1, 3])

        with thumb_col:
            if img_exists:
                thumb = _crop_face(path, face, padding=15)
                st.image(thumb, use_container_width=True)

        with label_col:
            st.markdown(f"**Face #{i + 1}** — Pipeline: `{pipeline_pt}`")
            options = ["Homem", "Mulher", "Não é uma pessoa"]
            default = options.index(current_val) if current_val in options else 0
            chosen  = st.radio(
                label            = f"Face #{i + 1}",
                options          = options,
                index            = default,
                horizontal       = True,
                key              = f"radio_{key}",
                label_visibility = "collapsed",
            )
            if chosen:
                annotations[key] = chosen
                if chosen == "Não é uma pessoa":
                    st.caption("⚠️ Marcado como falsa deteção")
                else:
                    match_icon = "✅" if chosen == pipeline_pt else "❌"
                    st.caption(f"{match_icon} {'Match' if chosen == pipeline_pt else 'Mismatch'}")

        st.divider()

# Navigation buttons
col_prev, _, col_next = st.columns([1, 4, 1])
with col_prev:
    if st.button("← Previous", use_container_width=True, disabled=cover_idx == 0):
        st.session_state["current_cover_idx"] -= 1
        st.rerun()
with col_next:
    if st.button("Next →", use_container_width=True, disabled=cover_idx == len(covers) - 1):
        st.session_state["current_cover_idx"] += 1
        st.rerun()

# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

st.divider()
st.subheader("📥 Export to CSV")

df = _build_dataframe(sample, annotations)

filled   = df["Face Correta"].notna() & (df["Face Correta"] != "")
n_filled = filled.sum()
n_total  = len(df)

if n_filled > 0:
    correct  = (df.loc[filled, "Match"] == "TRUE").sum()
    accuracy = correct / n_filled * 100
    c1, c2, c3 = st.columns(3)
    c1.metric("Faces labelled",   f"{n_filled} / {n_total}")
    c2.metric("Correct (Match)",  f"{correct}")
    c3.metric("Accuracy",         f"{accuracy:.1f}%")

col_preview, col_download = st.columns([3, 1])
with col_preview:
    st.dataframe(df, use_container_width=True, hide_index=True)
with col_download:
    st.download_button(
        label     = "⬇️ Download CSV",
        data      = df.to_csv(index=False, sep=",").encode("utf-8-sig"),
        file_name = "gema_accuracy_audit.csv",
        mime      = "text/csv",
        use_container_width=True,
    )
