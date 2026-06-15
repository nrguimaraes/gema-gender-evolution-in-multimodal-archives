"""
GEMA — Cover Annotation Tool
Manually classify female faces on covers as 'athlete' or 'non_athlete'.
Saves person_type directly into covers_analysis in MongoDB.

Run: streamlit run dashboard/annotate_covers.py
"""
import os
import sys
import streamlit as st
from pymongo import MongoClient
from PIL import Image, ImageDraw
import pandas as pd

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

MONGO_URI = os.environ.get("MONGO_URI", "mongodb://172.17.16.1:27017/")
DB_NAME   = "estagio_desporto"

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
IMG_DIR      = os.path.join(PROJECT_ROOT, "data", "capas", "images")

st.set_page_config(
    page_title="GEMA · Cover Annotation",
    page_icon="🏷️",
    layout="centered",
)

# ---------------------------------------------------------------------------
# DB
# ---------------------------------------------------------------------------

@st.cache_resource
def get_db():
    return MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)[DB_NAME]


def _img_path(source: str, date: str) -> str:
    fname = f"{source}_{str(date)[:10]}.jpg"
    return os.path.join(IMG_DIR, fname)


def _load_covers():
    """Return all covers that have at least one female face, with annotation progress."""
    db = get_db()
    covers = list(db["covers_analysis"].find(
        {"faces_detected.gender": "Woman"},
        {"source": 1, "date": 1, "year": 1, "faces_detected": 1}
    ).sort([("year", 1), ("date", 1)]))
    return covers


def _save_annotation(doc_id, face_index: int, label: str):
    """Write person_type into the specific face in the faces_detected array."""
    db = get_db()
    db["covers_analysis"].update_one(
        {"_id": doc_id},
        {"$set": {f"faces_detected.{face_index}.person_type": label}},
    )


def _annotation_progress(covers):
    """Count how many female faces have been annotated."""
    total_female  = sum(
        sum(1 for f in c["faces_detected"] if f.get("gender") == "Woman")
        for c in covers
    )
    annotated = sum(
        sum(1 for f in c["faces_detected"]
            if f.get("gender") == "Woman" and f.get("person_type") is not None)
        for c in covers
    )
    return annotated, total_female


# ---------------------------------------------------------------------------
# Draw bounding boxes on image
# ---------------------------------------------------------------------------

def _draw_faces(img_path: str, faces: list, highlight_idx: int | None = None) -> Image.Image:
    """Draw bounding boxes on the cover image. Highlight the face being annotated."""
    img = Image.open(img_path).convert("RGB")
    draw = ImageDraw.Draw(img)

    for i, face in enumerate(faces):
        if face.get("gender") != "Woman":
            continue
        x1, y1, x2, y2 = face["bbox"]
        already = face.get("person_type")

        if i == highlight_idx:
            color, width = "#FF4B4B", 5   # red = current face
        elif already == "athlete":
            color, width = "#2ecc71", 3   # green
        elif already == "publicity":
            color, width = "#9467bd", 3   # purple
        elif already == "other":
            color, width = "#f39c12", 3   # orange
        elif already == "not_woman":
            color, width = "#555555", 3   # dark grey
        else:
            color, width = "#1f77b4", 2   # blue = pending

        draw.rectangle([x1, y1, x2, y2], outline=color, width=width)

        # Small label
        label_text = already if already else "?"
        draw.text((x1, max(0, y1 - 14)), label_text, fill=color)

    return img


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------

st.title("🏷️ GEMA — Cover Annotation Tool")
st.caption("Classify each female face detected on front covers.")

covers = _load_covers()
annotated, total = _annotation_progress(covers)

st.progress(annotated / total if total else 0,
            text=f"Progress: {annotated} / {total} female faces annotated")

if annotated == total:
    st.success("✅ All female faces have been annotated! The Q2 filter in the dashboard is now fully calibrated.")
    st.stop()

st.divider()

# --- Sidebar controls ---
with st.sidebar:
    st.header("Navigation")
    show_all = st.checkbox("Show already annotated covers too", value=False)

    st.divider()
    st.markdown("**Legend**")
    st.markdown(
        "🟥 Current face  \n"
        "🟢 Athlete  \n"
        "🟣 Publicity / model  \n"
        "🟠 Other (fan, background…)  \n"
        "⚫ Not a woman (misdetection)  \n"
        "🔵 Pending"
    )

# Build list of (cover, face_index) pairs that still need annotation
pending = []
for cover in covers:
    for i, face in enumerate(cover["faces_detected"]):
        if face.get("gender") != "Woman":
            continue
        if face.get("person_type") is not None and not show_all:
            continue
        pending.append((cover, i))

if not pending:
    st.info("No covers pending annotation with current filters. Try unchecking 'Skip tiny faces'.")
    st.stop()

# --- Navigation state ---
if "ann_idx" not in st.session_state:
    st.session_state.ann_idx = 0

idx = st.session_state.ann_idx % len(pending)
cover, face_idx = pending[idx]

face      = cover["faces_detected"][face_idx]
img_path  = _img_path(cover["source"], cover["date"])
pct       = face.get("cover_coverage_percentage", 0)
conf      = face.get("gender_confidence", 0)
already   = face.get("person_type")

# --- Show cover ---
col_img, col_info = st.columns([3, 2])

with col_img:
    if os.path.exists(img_path):
        img = _draw_faces(img_path, cover["faces_detected"], highlight_idx=face_idx)
        st.image(img, caption=f"{cover['source']} · {str(cover['date'])[:10]}", use_container_width=True)
    else:
        st.warning(f"Image not found: {img_path}")

with col_info:
    st.markdown(f"**Source:** {cover['source']}")
    st.markdown(f"**Date:** {str(cover['date'])[:10]}")
    st.markdown(f"**Year:** {cover.get('year')}")
    st.markdown(f"**Face #{face_idx + 1}** of {sum(1 for f in cover['faces_detected'] if f.get('gender') == 'Woman')} female faces")
    st.markdown(f"**Cover area:** {pct:.2f}%")
    st.markdown(f"**Gender confidence:** {conf:.1f}%")

    if already:
        st.info(f"Already classified as: **{already}**")

    st.divider()
    st.markdown("**Who is this person?**")

    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("🏅 Athlete", use_container_width=True, type="primary"):
            _save_annotation(cover["_id"], face_idx, "athlete")
            st.session_state.ann_idx += 1
            st.rerun()
    with col_b:
        if st.button("📢 Publicity / model", use_container_width=True):
            _save_annotation(cover["_id"], face_idx, "publicity")
            st.session_state.ann_idx += 1
            st.rerun()

    col_c, col_d = st.columns(2)
    with col_c:
        if st.button("👥 Other (fan, background…)", use_container_width=True):
            _save_annotation(cover["_id"], face_idx, "other")
            st.session_state.ann_idx += 1
            st.rerun()
    with col_d:
        if st.button("🚫 Not a woman (misdetection)", use_container_width=True):
            _save_annotation(cover["_id"], face_idx, "not_woman")
            st.session_state.ann_idx += 1
            st.rerun()

    if st.button("⏭️ Skip (decide later)", use_container_width=True):
        st.session_state.ann_idx += 1
        st.rerun()

st.divider()
st.caption(f"Showing cover {idx + 1} of {len(pending)} pending · {annotated}/{total} total annotated")

# Navigation
col_prev, col_next = st.columns(2)
with col_prev:
    if st.button("← Previous"):
        st.session_state.ann_idx = max(0, st.session_state.ann_idx - 1)
        st.rerun()
with col_next:
    if st.button("Next →"):
        st.session_state.ann_idx += 1
        st.rerun()
