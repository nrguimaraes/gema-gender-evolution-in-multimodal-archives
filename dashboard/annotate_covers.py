"""
GEMA — Cover Annotation Tool
Classify every face detected on covers (both genders):
  - athlete / publicity / other / misdetection
Saves person_type and any gender corrections directly into covers_analysis (MongoDB).

Run: streamlit run dashboard/annotate_covers.py
"""
import os
import streamlit as st
from pymongo import MongoClient
from PIL import Image, ImageDraw

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
# DB helpers
# ---------------------------------------------------------------------------

@st.cache_resource
def get_db():
    return MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)[DB_NAME]


def _img_path(source: str, date: str) -> str:
    return os.path.join(IMG_DIR, f"{source}_{str(date)[:10]}.jpg")


def _load_covers(gender_filter: str):
    """
    Return covers that have at least one face matching the gender filter.
    gender_filter: 'Woman', 'Man', or 'Both'
    """
    db = get_db()
    if gender_filter == "Both":
        query = {"faces_detected": {"$exists": True, "$ne": []}}
    else:
        opposite = "Man" if gender_filter == "Woman" else "Woman"
        query = {"$or": [
            {"faces_detected.gender": gender_filter},
            # also include faces corrected FROM this gender
            {"faces_detected.gender_corrected": gender_filter},
        ]}
    return list(db["covers_analysis"].find(
        query,
        {"source": 1, "date": 1, "year": 1, "faces_detected": 1}
    ).sort([("year", 1), ("date", 1)]))


def _save_annotation(doc_id, face_index: int, label: str, original_gender: str):
    """
    Persist person_type for a face. If label is a misdetection, flip gender in DB
    and record the original so the reset can undo it.
    """
    db = get_db()
    fields = {f"faces_detected.{face_index}.person_type": label}
    if label == "not_woman":
        fields[f"faces_detected.{face_index}.gender"] = "Man"
        fields[f"faces_detected.{face_index}.gender_corrected"] = "Woman"  # original
    elif label == "not_man":
        fields[f"faces_detected.{face_index}.gender"] = "Woman"
        fields[f"faces_detected.{face_index}.gender_corrected"] = "Man"    # original
    db["covers_analysis"].update_one({"_id": doc_id}, {"$set": fields})


def _is_target_face(face: dict, gender_filter: str) -> bool:
    """True if this face should be annotated under the current gender tab."""
    g = face.get("gender")
    corrected = face.get("gender_corrected")  # stores the original gender before correction
    if gender_filter == "Woman":
        # current gender is Woman, OR was Woman and got corrected to Man
        return g == "Woman" or corrected == "Woman"
    elif gender_filter == "Man":
        return g == "Man" or corrected == "Man"
    else:
        return True


def _annotation_progress(covers, gender_filter):
    total = sum(
        sum(1 for f in c["faces_detected"] if _is_target_face(f, gender_filter))
        for c in covers
    )
    annotated = sum(
        sum(1 for f in c["faces_detected"]
            if _is_target_face(f, gender_filter) and f.get("person_type") is not None)
        for c in covers
    )
    return annotated, total


def _misdetection_counts():
    """Count confirmed misdetections stored in the DB."""
    db = get_db()
    pipeline = [
        {"$unwind": "$faces_detected"},
        {"$match": {"faces_detected.person_type": {"$in": ["not_woman", "not_man"]}}},
        {"$group": {"_id": "$faces_detected.person_type", "count": {"$sum": 1}}}
    ]
    results = {r["_id"]: r["count"] for r in db["covers_analysis"].aggregate(pipeline)}
    return results.get("not_woman", 0), results.get("not_man", 0)


# ---------------------------------------------------------------------------
# Drawing
# ---------------------------------------------------------------------------

COLORS = {
    "highlight":   "#FF4B4B",
    "athlete":     "#2ecc71",
    "publicity":   "#9467bd",
    "other":       "#f39c12",
    "not_woman":   "#555555",
    "not_man":     "#555555",
    "pending":     "#1f77b4",
}

def _draw_faces(img_path: str, faces: list, highlight_idx: int, gender_filter: str) -> Image.Image:
    img = Image.open(img_path).convert("RGB")
    draw = ImageDraw.Draw(img)
    for i, face in enumerate(faces):
        if not _is_target_face(face, gender_filter):
            continue
        x1, y1, x2, y2 = face["bbox"]
        pt = face.get("person_type")
        if i == highlight_idx:
            color, width = COLORS["highlight"], 5
        elif pt in COLORS:
            color, width = COLORS[pt], 3
        else:
            color, width = COLORS["pending"], 2
        draw.rectangle([x1, y1, x2, y2], outline=color, width=width)
        draw.text((x1, max(0, y1 - 14)), pt if pt else "?", fill=color)
    return img


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------

st.title("🏷️ GEMA — Cover Annotation Tool")

# --- Tabs for gender selection ---
tab_w, tab_m, tab_stats = st.tabs(["👩 Female faces", "👨 Male faces", "📊 Stats"])

def _render_annotation_tab(gender_filter: str, misdetection_label: str, misdetection_btn: str):
    covers = _load_covers(gender_filter)
    annotated, total = _annotation_progress(covers, gender_filter)

    st.progress(
        annotated / total if total else 0,
        text=f"Progress: {annotated} / {total} faces annotated"
    )

    show_all = st.checkbox("Show already annotated covers too", value=False, key=f"show_all_{gender_filter}")

    if annotated == total and total > 0 and not show_all:
        st.success(f"✅ All {gender_filter.lower()} faces have been annotated!")
        return

    # Build pending list
    pending = []
    for cover in covers:
        for i, face in enumerate(cover["faces_detected"]):
            if not _is_target_face(face, gender_filter):
                continue
            if face.get("person_type") is not None and not show_all:
                continue
            pending.append((cover, i))

    if not pending:
        st.info("No faces pending annotation.")
        return

    nav_key = f"ann_idx_{gender_filter}"
    if nav_key not in st.session_state:
        st.session_state[nav_key] = 0

    idx = st.session_state[nav_key] % len(pending)
    cover, face_idx = pending[idx]
    face     = cover["faces_detected"][face_idx]
    img_path = _img_path(cover["source"], cover["date"])
    pct      = face.get("cover_coverage_percentage", 0)
    conf     = face.get("gender_confidence", 0)
    already  = face.get("person_type")
    original_gender = face.get("gender")

    col_img, col_info = st.columns([3, 2])

    with col_img:
        if os.path.exists(img_path):
            img = _draw_faces(img_path, cover["faces_detected"], face_idx, gender_filter)
            st.image(img, caption=f"{cover['source']} · {str(cover['date'])[:10]}", use_container_width=True)
        else:
            st.warning(f"Image not found: {img_path}")

    with col_info:
        st.markdown(f"**Source:** {cover['source']}")
        st.markdown(f"**Date:** {str(cover['date'])[:10]}")
        st.markdown(f"**Year:** {cover.get('year')}")
        n_gender = sum(1 for f in cover["faces_detected"] if _is_target_face(f, gender_filter))
        st.markdown(f"**Face #{face_idx + 1}** of {n_gender} {gender_filter.lower()} faces on this cover")
        st.markdown(f"**Cover area:** {pct:.2f}%")
        st.markdown(f"**Gender confidence:** {conf:.1f}%")

        if already:
            st.info(f"Already classified as: **{already}**")

        st.divider()
        st.markdown("**Who is this person?**")

        col_a, col_b = st.columns(2)
        with col_a:
            if st.button("🏅 Athlete", use_container_width=True, type="primary", key=f"ath_{gender_filter}_{idx}"):
                _save_annotation(cover["_id"], face_idx, "athlete", original_gender)
                st.session_state[nav_key] += 1
                st.rerun()
        with col_b:
            if st.button("📢 Publicity / model", use_container_width=True, key=f"pub_{gender_filter}_{idx}"):
                _save_annotation(cover["_id"], face_idx, "publicity", original_gender)
                st.session_state[nav_key] += 1
                st.rerun()

        col_c, col_d = st.columns(2)
        with col_c:
            if st.button("👥 Other (fan, background…)", use_container_width=True, key=f"oth_{gender_filter}_{idx}"):
                _save_annotation(cover["_id"], face_idx, "other", original_gender)
                st.session_state[nav_key] += 1
                st.rerun()
        with col_d:
            if st.button(misdetection_btn, use_container_width=True, key=f"mis_{gender_filter}_{idx}"):
                _save_annotation(cover["_id"], face_idx, misdetection_label, original_gender)
                st.session_state[nav_key] += 1
                st.rerun()

        if st.button("⏭️ Skip (decide later)", use_container_width=True, key=f"skip_{gender_filter}_{idx}"):
            st.session_state[nav_key] += 1
            st.rerun()

    st.divider()
    st.caption(f"Showing {idx + 1} of {len(pending)} pending · {annotated}/{total} total annotated")

    col_prev, col_next = st.columns(2)
    with col_prev:
        if st.button("← Previous", key=f"prev_{gender_filter}"):
            st.session_state[nav_key] = max(0, st.session_state[nav_key] - 1)
            st.rerun()
    with col_next:
        if st.button("Next →", key=f"next_{gender_filter}"):
            st.session_state[nav_key] += 1
            st.rerun()


with tab_w:
    _render_annotation_tab("Woman", "not_woman", "🚫 Not a woman (misdetection)")

with tab_m:
    _render_annotation_tab("Man", "not_man", "🚫 Not a man (misdetection)")

with tab_stats:
    st.subheader("📊 Annotation Summary")

    not_woman_count, not_man_count = _misdetection_counts()

    col1, col2 = st.columns(2)
    col1.metric("Detected as Woman → actually Man", not_woman_count,
                help="Faces the model classified as female that were manually corrected to male")
    col2.metric("Detected as Man → actually Woman", not_man_count,
                help="Faces the model classified as male that were manually corrected to female")

    st.divider()

    # Full breakdown per person_type
    db = get_db()
    pipeline = [
        {"$unwind": "$faces_detected"},
        {"$match": {"faces_detected.person_type": {"$exists": True}}},
        {"$group": {
            "_id": {
                "gender": "$faces_detected.gender",
                "person_type": "$faces_detected.person_type"
            },
            "count": {"$sum": 1}
        }},
        {"$sort": {"_id.gender": 1, "count": -1}}
    ]
    rows = list(db["covers_analysis"].aggregate(pipeline))
    if rows:
        import pandas as pd
        df = pd.DataFrame([{
            "Gender": r["_id"]["gender"],
            "Category": r["_id"]["person_type"],
            "Count": r["count"]
        } for r in rows])
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("No annotations yet.")

    st.divider()
    st.markdown("**Reset all annotations**")
    st.caption("Clears all person_type labels and restores original genders. Use to start over.")
    if st.button("Reset all annotations", type="secondary"):
        db_conn = get_db()
        # Restore gender for any corrected faces
        for original in ["Woman", "Man"]:
            db_conn["covers_analysis"].update_many(
                {"faces_detected.gender_corrected": original},
                {"$set":   {f"faces_detected.$[f].gender": original},
                 "$unset": {"faces_detected.$[f].gender_corrected": ""}},
                array_filters=[{"f.gender_corrected": original}],
            )
        # Remove all person_type labels
        db_conn["covers_analysis"].update_many(
            {"faces_detected.person_type": {"$exists": True}},
            {"$unset": {"faces_detected.$[f].person_type": ""}},
            array_filters=[{"f.person_type": {"$exists": True}}],
        )
        st.success("All annotations cleared.")
        st.cache_data.clear()
        st.rerun()
