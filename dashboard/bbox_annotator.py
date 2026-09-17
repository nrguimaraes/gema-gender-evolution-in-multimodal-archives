"""
GEMA — Manual Bounding Box Annotator (Phase 2)
Shows pipeline-detected faces and lets the user draw bounding boxes
around faces the pipeline missed, using Plotly box-select + st.plotly_chart.

Annotations are stored in `covers_manual_bbox` (never touches `covers_analysis`).

Run: streamlit run dashboard/bbox_annotator.py
"""
import base64
import io
import os
import random

import plotly.graph_objects as go
import streamlit as st
from pymongo import MongoClient
from PIL import Image, ImageDraw

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

MONGO_URI = os.environ.get("MONGO_URI", "mongodb://172.17.16.1:27017/")
DB_NAME   = "estagio_desporto"
SRC_COL   = "covers_analysis"
DEST_COL  = "covers_manual_bbox"

NEWSPAPERS = ["a-bola", "o-jogo", "record"]
LABELS     = {"a-bola": "A Bola", "o-jogo": "O Jogo", "record": "Record"}
N_COVERS   = 5
DISPLAY_W  = 680

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
IMG_DIR      = os.path.join(PROJECT_ROOT, "data", "capas", "images")

PIPELINE_COLORS = {"Woman": "#e377c2", "Man": "#1f77b4", "?": "#aaaaaa"}

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(page_title="GEMA · BBox Annotator", page_icon="🖊️", layout="wide")

st.markdown("""
<style>
.block-container{padding-top:1.2rem}
h1{font-size:1.5rem!important}
.lb{display:inline-block;width:14px;height:14px;border-radius:2px;
    margin-right:4px;vertical-align:middle}
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

@st.cache_resource
def get_db():
    return MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)[DB_NAME]


@st.cache_data(ttl=300)
def load_sample(seed: int) -> dict:
    db  = get_db()
    rng = random.Random(seed)
    out = {}
    for np_ in NEWSPAPERS:
        docs = list(db[SRC_COL].find(
            {"source": np_, "faces_detected": {"$exists": True}},
            {"source": 1, "date": 1, "year": 1, "faces_detected": 1}
        ))
        sel = rng.sample(docs, min(N_COVERS, len(docs)))
        sel.sort(key=lambda c: str(c["date"]))
        out[np_] = sel
    return out


def load_existing(cover_id) -> list:
    doc = get_db()[DEST_COL].find_one({"cover_id": str(cover_id)})
    return doc.get("manual_faces", []) if doc else []


def save_boxes(cover_doc, manual_faces: list, notes: str = ""):
    get_db()[DEST_COL].update_one(
        {"cover_id": str(cover_doc["_id"])},
        {"$set": {
            "cover_id":     str(cover_doc["_id"]),
            "source":       cover_doc["source"],
            "date":         str(cover_doc["date"])[:10],
            "year":         cover_doc.get("year"),
            "manual_faces": manual_faces,
            "notes":        notes,
        }},
        upsert=True,
    )


def img_path(source: str, date) -> str:
    return os.path.join(IMG_DIR, f"{source}_{str(date)[:10]}.jpg")

# ---------------------------------------------------------------------------
# Image helpers
# ---------------------------------------------------------------------------

def draw_pipeline(img: Image.Image, faces: list, scale: float = 1.0) -> Image.Image:
    draw = ImageDraw.Draw(img)
    for i, face in enumerate(faces):
        x1, y1, x2, y2 = [int(v * scale) for v in face.get("bbox", [0, 0, 0, 0])]
        color = PIPELINE_COLORS.get(face.get("gender", "?"), "#aaaaaa")
        draw.rectangle([x1, y1, x2, y2], outline=color, width=3)
        lbl = f"#{i+1} {face.get('gender','?')[:1]}"
        draw.rectangle([x1, y1-16, x1+len(lbl)*8, y1], fill=color)
        draw.text((x1+2, y1-14), lbl, fill="white")
    return img


def pil_to_b64(img: Image.Image) -> str:
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return base64.b64encode(buf.getvalue()).decode()


def resize_to(img: Image.Image, width: int):
    w, h  = img.size
    scale = width / w
    return img.resize((width, int(h * scale)), Image.LANCZOS), scale

# ---------------------------------------------------------------------------
# Plotly annotation figure
# ---------------------------------------------------------------------------

def make_figure(img_b64: str, disp_w: int, disp_h: int, boxes: list) -> go.Figure:
    """
    Image shown as Plotly layout image.
    y-axis is flipped (0 = top) so pixel coords match plot coords directly.
    dragmode='select' lets user drag a box; on_select returns the box range.
    """
    fig = go.Figure()

    fig.add_layout_image(
        source=f"data:image/jpeg;base64,{img_b64}",
        x=0, y=0,
        xref="x", yref="y",
        xanchor="left", yanchor="top",
        sizex=disp_w, sizey=disp_h,
        sizing="stretch",
        layer="below",
    )

    # Invisible scatter at corners + center — required for box-select to fire
    fig.add_trace(go.Scatter(
        x=[0, disp_w//2, disp_w, 0,       disp_w],
        y=[0, disp_h//2, 0,       disp_h,  disp_h],
        mode="markers",
        marker=dict(size=1, opacity=0),
        hoverinfo="skip",
        showlegend=False,
    ))

    # Draw confirmed manual boxes
    colors = ["#2ca02c", "#17becf", "#bcbd22", "#9467bd", "#ff7f0e"]
    for i, b in enumerate(boxes):
        c = colors[i % len(colors)]
        fig.add_shape(
            type="rect",
            x0=b["x1"], y0=b["y1"], x1=b["x2"], y1=b["y2"],
            xref="x", yref="y",
            line=dict(color=c, width=3),
            fillcolor=c.replace("#", "rgba(") + ",0.15)" if False else "rgba(44,160,44,0.15)",
        )
        fig.add_annotation(
            x=b["x1"], y=b["y1"] - 4,
            text=f"<b>M#{i+1}</b>",
            showarrow=False,
            bgcolor="#2ca02c",
            font=dict(color="white", size=11),
            xanchor="left", yanchor="bottom",
            xref="x", yref="y",
        )

    fig.update_layout(
        width=disp_w,
        height=disp_h,
        margin=dict(l=0, r=0, t=0, b=0),
        xaxis=dict(
            range=[0, disp_w], showgrid=False, zeroline=False,
            visible=False, fixedrange=True,
        ),
        yaxis=dict(
            range=[disp_h, 0],  # flipped: 0 at top = pixel top
            showgrid=False, zeroline=False,
            visible=False, fixedrange=True, scaleanchor="x",
        ),
        dragmode="select",
        selectdirection="d",
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        hovermode=False,
        newselection_line_color="#2ca02c",
        newselection_line_width=2,
    )

    return fig

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

with st.sidebar:
    st.title("🖊️ BBox Annotator")
    st.caption("Drag on the image to draw a selection box around each missed face.")
    st.divider()

    seed   = st.number_input("Random seed", min_value=1, max_value=9999, value=42, step=1)
    sample = load_sample(seed)

    newspaper    = st.selectbox("Newspaper", NEWSPAPERS, format_func=lambda x: LABELS[x])
    covers       = sample[newspaper]
    cover_labels = [f"Cover {i+1} · {str(c['date'])[:10]}" for i, c in enumerate(covers)]
    cover_choice = st.radio("Select cover", cover_labels)
    cover_idx    = cover_labels.index(cover_choice)
    cover        = covers[cover_idx]

    st.divider()
    db_conn       = get_db()
    annotated_ids = set(str(d["cover_id"]) for d in db_conn[DEST_COL].find({}, {"cover_id": 1}))
    all_ids       = [str(c["_id"]) for news in sample.values() for c in news]
    done          = sum(1 for cid in all_ids if cid in annotated_ids)
    st.progress(done / len(all_ids) if all_ids else 0,
                text=f"{done} / {len(all_ids)} covers annotated")
    st.divider()
    st.caption("Saved to `covers_manual_bbox`.")

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

path       = img_path(cover["source"], cover["date"])
faces      = cover.get("faces_detected", [])
cover_name = f"{LABELS[newspaper]} · {str(cover['date'])[:10]}"
cover_done = str(cover["_id"]) in annotated_ids
existing   = load_existing(cover["_id"])

st.title(f"🖊️ {cover_name}")
if cover_done:
    st.success(f"Already annotated ({len(existing)} box(es)). Update below if needed.")

st.markdown(
    "<b>Pipeline:</b> "
    "<span class='lb' style='background:#e377c2'></span>Woman &nbsp;"
    "<span class='lb' style='background:#1f77b4'></span>Man &nbsp;&nbsp;"
    "<b>Manual boxes:</b> <span style='color:#2ca02c'><b>green</b></span>",
    unsafe_allow_html=True,
)
st.info("**How to annotate:** Drag on the image to select a box around a missed face, "
        "then click **Confirm** on the right to add it. Repeat for each face.")
st.divider()

if not os.path.exists(path):
    st.error(f"Image not found: `{path}`")
    st.stop()

orig_img       = Image.open(path).convert("RGB")
orig_w, orig_h = orig_img.size

# Build display image once per cover
bg_key = f"bg_{cover['_id']}"
if bg_key not in st.session_state:
    _disp, _sc = resize_to(orig_img.copy(), DISPLAY_W)
    _disp = draw_pipeline(_disp, faces, scale=_sc)
    st.session_state[bg_key] = (pil_to_b64(_disp), _disp.size[0], _disp.size[1], _sc)

img_b64, disp_w, disp_h, scale = st.session_state[bg_key]

# Session state: list of confirmed boxes in display coords
boxes_key = f"boxes_{cover['_id']}"
if boxes_key not in st.session_state:
    st.session_state[boxes_key] = [
        {"x1": int(f["bbox_original"][0]*scale), "y1": int(f["bbox_original"][1]*scale),
         "x2": int(f["bbox_original"][2]*scale), "y2": int(f["bbox_original"][3]*scale)}
        for f in existing
    ]

boxes: list = st.session_state[boxes_key]

# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------

col_fig, col_form = st.columns([3, 2])

with col_fig:
    fig = make_figure(img_b64, disp_w, disp_h, boxes)

    event = st.plotly_chart(
        fig,
        use_container_width=False,
        on_select="rerun",
        selection_mode=("box",),
        key=f"plot_{cover['_id']}",
    )

# ---------------------------------------------------------------------------
# Right column
# ---------------------------------------------------------------------------

with col_form:
    st.markdown("**Pipeline detections (reference)**")
    if not faces:
        st.caption("No pipeline detections on this cover.")
    else:
        for i, face in enumerate(faces):
            g  = face.get("gender", "?")
            pt = face.get("person_type", "not annotated")
            bb = face.get("bbox", [0, 0, 0, 0])
            ic = "🩷" if g == "Woman" else "💙" if g == "Man" else "❔"
            st.caption(f"{ic} **#{i+1}** {g} · {pt} · ({bb[0]},{bb[1]})→({bb[2]},{bb[3]})")

    st.divider()

    # Pending selection from plot
    pending = None
    try:
        sel = event.selection.box  # type: ignore
        if sel:
            xr = sel[0]["x"]
            yr = sel[0]["y"]
            pending = {
                "x1": int(min(xr)), "y1": int(min(yr)),
                "x2": int(max(xr)), "y2": int(max(yr)),
            }
    except Exception:
        pass

    if pending:
        st.markdown("**Selected area — confirm to add:**")
        st.code(f"({pending['x1']},{pending['y1']}) → ({pending['x2']},{pending['y2']})")
        if st.button("✅ Confirm box", type="primary", use_container_width=True):
            boxes.append(pending)
            st.session_state[boxes_key] = boxes
            st.rerun()
    else:
        st.markdown("**Drag on the image** to select an area,\nthen click Confirm here.")

    st.divider()

    # Label form for confirmed boxes
    lbl_key = f"labels_{cover['_id']}"
    if lbl_key not in st.session_state:
        st.session_state[lbl_key] = [
            {"gender": f.get("gender", "Woman"), "person_type": f.get("person_type", "athlete")}
            for f in existing
        ]
    labels: list = st.session_state[lbl_key]
    while len(labels) < len(boxes):
        labels.append({"gender": "Woman", "person_type": "athlete"})
    labels = labels[:len(boxes)]
    st.session_state[lbl_key] = labels

    n = len(boxes)
    if n == 0:
        st.caption("No manual boxes added yet.")
    else:
        st.markdown(f"**Label {n} box(es)**")
        to_remove = None
        for i in range(n):
            st.markdown(f"**Box M#{i+1}**")
            gc, tc, dc = st.columns([2, 2, 1])
            gender = gc.selectbox(
                "Gender", ["Woman", "Man", "Uncertain"],
                index=["Woman", "Man", "Uncertain"].index(labels[i].get("gender", "Woman")),
                key=f"g_{cover['_id']}_{i}",
            )
            ptype = tc.selectbox(
                "Person type", ["athlete", "publicity/model", "fan/other", "uncertain"],
                index=["athlete", "publicity/model", "fan/other", "uncertain"].index(
                    labels[i].get("person_type", "athlete")),
                key=f"t_{cover['_id']}_{i}",
            )
            if dc.button("🗑", key=f"del_{cover['_id']}_{i}"):
                to_remove = i
            labels[i] = {"gender": gender, "person_type": ptype}

        if to_remove is not None:
            boxes.pop(to_remove)
            labels.pop(to_remove)
            st.session_state[boxes_key] = boxes
            st.session_state[lbl_key]   = labels
            st.rerun()

    st.session_state[lbl_key] = labels

    st.divider()

    nk = f"notes_{cover['_id']}"
    if nk not in st.session_state:
        doc = get_db()[DEST_COL].find_one({"cover_id": str(cover["_id"])})
        st.session_state[nk] = doc.get("notes", "") if doc else ""

    notes = st.text_area("Notes (optional)", value=st.session_state[nk],
                         key=f"ni_{cover['_id']}")

    if st.button(f"💾 Save {n} box(es)" if n else "💾 Save (mark as reviewed)",
                 type="primary", use_container_width=True):
        manual_faces = []
        for i, b in enumerate(boxes):
            lbl = labels[i] if i < len(labels) else {}
            manual_faces.append({
                "bbox_original": [
                    max(0, int(b["x1"]/scale)), max(0, int(b["y1"]/scale)),
                    min(orig_w, int(b["x2"]/scale)), min(orig_h, int(b["y2"]/scale)),
                ],
                "gender":      lbl.get("gender", "Woman"),
                "person_type": lbl.get("person_type", "athlete"),
            })
        save_boxes(cover, manual_faces, notes)
        st.success(f"Saved {n} box(es) for {cover_name}.")
        st.cache_data.clear()
        st.rerun()

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

st.divider()
with st.expander("Annotation summary"):
    all_docs = list(db_conn[DEST_COL].find(
        {}, {"source": 1, "date": 1, "manual_faces": 1, "notes": 1}
    ))
    if not all_docs:
        st.info("No annotations saved yet.")
    else:
        import pandas as pd
        rows = []
        for doc in all_docs:
            mf = doc.get("manual_faces", [])
            rows.append({
                "Source": LABELS.get(doc.get("source",""), doc.get("source","")),
                "Date":   doc.get("date",""),
                "Boxes":  len(mf),
                "Women":  sum(1 for f in mf if f.get("gender")=="Woman"),
                "Men":    sum(1 for f in mf if f.get("gender")=="Man"),
                "Notes":  doc.get("notes",""),
            })
        df = pd.DataFrame(rows).sort_values(["Source","Date"])
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.metric("Total missed faces annotated", int(df["Boxes"].sum()))
