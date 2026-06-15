"""
GEMA — Gender Evolution in Multimodal Archives
Interactive demonstrator dashboard built with Streamlit and Plotly.
Run: streamlit run dashboard/app_dashboard.py
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import numpy as np
import yake

import db

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="GEMA · Gender Evolution in Multimodal Archives",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    .block-container { padding-top: 1.5rem; }
    h1 { font-size: 1.6rem !important; }
    .stTabs [data-baseweb="tab"] { font-size: 0.9rem; }
    .insight-box { background:#f0f2f6; border-left:4px solid #9467bd;
                   padding:0.75rem 1rem; border-radius:4px; margin:0.5rem 0; }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Reference data
# ---------------------------------------------------------------------------

OLYMPICS = {2000: "Sydney", 2004: "Athens", 2008: "Beijing",
            2012: "London", 2016: "Rio", 2021: "Tokyo", 2024: "Paris"}
MENS_WORLD_CUPS   = {2002, 2006, 2010, 2014, 2018, 2022}
WOMENS_WORLD_CUPS = {1999, 2003, 2007, 2011, 2015, 2019, 2023}
EURO_CUPS         = {2000, 2004, 2008, 2012, 2016, 2020, 2024}

ALL_SOURCES = ["A Bola", "Record", "O Jogo", "SAPO", "Notícias ao Minuto", "ZAP", "Euronews", "Flashscore"]
PRINT_SOURCES = ["A Bola", "Record", "O Jogo"]

SOURCE_COLORS = {
    "A Bola":            "#e41a1c",
    "Record":            "#377eb8",
    "O Jogo":            "#4daf4a",
    "SAPO":              "#ff7f00",
    "Notícias ao Minuto":"#984ea3",
    "ZAP":               "#a65628",
    "Euronews":          "#f781bf",
    "Flashscore":        "#999999",
}

# ---------------------------------------------------------------------------
# Sidebar — global filters
# ---------------------------------------------------------------------------

with st.sidebar:
    st.title("GEMA")
    st.caption("Gender Evolution in Multimodal Archives · 1998–2024")
    st.divider()

    year_range = st.slider(
        "Year range",
        min_value=1998, max_value=2024,
        value=(2016, 2024),
    )

    selected_sources = st.multiselect(
        "Sources",
        options=ALL_SOURCES,
        default=ALL_SOURCES,
        help="Select which news sources to include in the analysis.",
    )
    if not selected_sources:
        selected_sources = ALL_SOURCES

    st.divider()
    st.markdown("**Events to highlight on charts**")
    show_olympics  = st.checkbox("Olympic Games",       value=True)
    show_mens_wc   = st.checkbox("Men's World Cup",     value=True)
    show_womens_wc = st.checkbox("Women's World Cup",   value=False)
    show_euros     = st.checkbox("UEFA Euro",           value=False)

    st.divider()
    _prom_threshold = getattr(db, "PROMINENCE_THRESHOLD", 1.0)
    filter_fp = st.checkbox(
        "Show only prominent faces (editorial subjects)",
        value=False,
        help=(
            f"Keep only faces that cover ≥{_prom_threshold}% of the cover page. "
            "These are almost certainly the intended editorial subject, not incidental detections."
        ),
    )

    st.divider()
    st.caption("🔬 CC3051 · GEMA · 2025")

# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

with st.spinner("Loading data from database…"):
    df_vis_raw   = db.fetch_visual_yearly(filter_fp=filter_fp)
    df_txt_raw   = db.fetch_text_yearly()
    df_corr      = db.fetch_visual_text_correlation()
    df_prom      = db.fetch_prominence_detail(filter_fp=filter_fp)
    df_ner       = db.fetch_top_entities(top_n=25)
    df_sports    = db.fetch_sports_breakdown()
    df_sports_yr = db.fetch_sports_by_year()
    df_ent_dist  = db.fetch_entity_distribution("feminine")
    df_sem       = db.fetch_semantic_keywords()


def _apply_filters(df, year_col="year", src_col="source"):
    if df.empty:
        return df
    mask = pd.Series([True] * len(df), index=df.index)
    if year_col in df.columns:
        mask &= df[year_col].between(*year_range)
    if src_col in df.columns:
        mask &= df[src_col].isin(selected_sources)
    return df[mask]


df_vis  = _apply_filters(df_vis_raw)
df_txt  = _apply_filters(df_txt_raw)
df_prom = _apply_filters(df_prom)

if not df_corr.empty and "year" in df_corr.columns:
    df_corr = df_corr[df_corr["year"].between(*year_range)]

# ---------------------------------------------------------------------------
# Header KPIs
# ---------------------------------------------------------------------------

st.title("GEMA — Gender Representation in Portuguese Sports Media")
st.caption(
    "Multimodal analysis (computer vision + NLP) of gender representation "
    "in Portuguese sports press — 1998 to 2024."
)


def _safe_female_pct(df, gender_col="gender", count_col="count"):
    if df.empty or gender_col not in df.columns:
        return 0.0
    tot = df[count_col].sum()
    fem = df.loc[df[gender_col] == "Woman", count_col].sum()
    return round(fem / tot * 100, 1) if tot else 0.0


vis_fem = _safe_female_pct(df_vis)
txt_fem = _safe_female_pct(df_txt, gender_col="text_gender")

k1, k2, k3, k4 = st.columns(4)
total_articles_in_range = int(df_txt["count"].sum()) if not df_txt.empty else 0
k1.metric("Female Faces (covers)",   f"{vis_fem}%")
k2.metric("Female Articles (text)",  f"{txt_fem}%")
k3.metric("Faces Detected",          f"{int(df_vis['count'].sum()):,}" if not df_vis.empty else "0")
k4.metric(
    f"Articles ({year_range[0]}–{year_range[1]})",
    f"{total_articles_in_range:,}",
    help=f"Total articles in the selected period ({year_range[0]}–{year_range[1]}) and sources. The full database contains 198,771 articles (1998–2024).",
)

st.divider()

# ---------------------------------------------------------------------------
# Event line helper
# ---------------------------------------------------------------------------

def add_event_lines(fig, y_max=100):
    for yr in range(year_range[0], year_range[1] + 1):
        if show_olympics and yr in OLYMPICS:
            fig.add_vline(x=yr, line_dash="dot", line_color="#d62728", line_width=1.8,
                          annotation_text=f"🏅 {OLYMPICS[yr]} {yr}",
                          annotation_position="top right", annotation_font_size=9)
        elif show_mens_wc and yr in MENS_WORLD_CUPS:
            fig.add_vline(x=yr, line_dash="dash", line_color="#ff7f0e", line_width=1.5,
                          annotation_text=f"⚽ Men's WC {yr}",
                          annotation_position="top right", annotation_font_size=9)
        elif show_womens_wc and yr in WOMENS_WORLD_CUPS:
            fig.add_vline(x=yr, line_dash="dash", line_color="#e377c2", line_width=1.5,
                          annotation_text=f"⚽ Women's WC {yr}",
                          annotation_position="top right", annotation_font_size=9)
        elif show_euros and yr in EURO_CUPS:
            fig.add_vline(x=yr, line_dash="longdash", line_color="#2ca02c", line_width=1.2,
                          annotation_text=f"🏆 Euro {yr}",
                          annotation_position="top right", annotation_font_size=9)
    return fig


tab1, tab2, tab3 = st.tabs([
    "📈 Evolution & Events",
    "👁️ Visual vs Textual",
    "🔍 Diversity & Context",
])


# ===========================================================================
# TAB 1 — Longitudinal evolution, mega-events, newspaper comparison
# ===========================================================================

with tab1:

    # -----------------------------------------------------------------------
    # Q1 — Longitudinal evolution
    # -----------------------------------------------------------------------
    st.subheader("Q1 · Longitudinal Evolution of Female Representation (1998–2024)")
    st.caption(
        "Annual percentage of female faces on front covers (visual axis) "
        "and female-dominant articles (textual axis)."
    )

    q1_axis = st.radio(
        "Show axis",
        ["Both", "Visual only", "Textual only"],
        horizontal=True,
        key="q1_radio",
    )

    def _yr_female_pct_vis(df):
        if df.empty:
            return pd.DataFrame(columns=["year", "female_pct"])
        piv = df.groupby(["year", "gender"])["count"].sum().unstack(fill_value=0).reset_index()
        w = piv.get("Woman", 0);  m = piv.get("Man", 0)
        piv["female_pct"] = w / (w + m).replace(0, float("nan")) * 100
        return piv[["year", "female_pct"]].dropna()

    def _yr_female_pct_txt(df):
        if df.empty:
            return pd.DataFrame(columns=["year", "female_pct"])
        piv = df.groupby(["year", "text_gender"])["count"].sum().unstack(fill_value=0).reset_index()
        w = piv.get("Woman", 0);  m = piv.get("Man", 0)
        piv["female_pct"] = w / (w + m).replace(0, float("nan")) * 100
        return piv[["year", "female_pct"]].dropna()

    vis_evo = _yr_female_pct_vis(df_vis)
    txt_evo = _yr_female_pct_txt(df_txt)

    if vis_evo.empty and txt_evo.empty:
        st.info("No data for the selected range and sources.")
    else:
        fig_q1 = go.Figure()

        if q1_axis in ("Both", "Visual only") and not vis_evo.empty:
            vis_evo["year"] = vis_evo["year"].astype(int)
            fig_q1.add_trace(go.Scatter(
                x=vis_evo["year"], y=vis_evo["female_pct"].round(2),
                mode="lines+markers", name="Visual · Covers",
                line=dict(color="#9467bd", width=3), marker=dict(size=8),
                connectgaps=True,
                hovertemplate="<b>%{x}</b><br>Visual: %{y:.1f}%<extra></extra>",
            ))

        if q1_axis in ("Both", "Textual only") and not txt_evo.empty:
            txt_evo["year"] = txt_evo["year"].astype(int)
            fig_q1.add_trace(go.Scatter(
                x=txt_evo["year"], y=txt_evo["female_pct"].round(2),
                mode="lines+markers", name="Textual · Articles",
                line=dict(color="#e377c2", width=3, dash="dot"), marker=dict(size=8),
                connectgaps=True,
                hovertemplate="<b>%{x}</b><br>Textual: %{y:.1f}%<extra></extra>",
            ))

        fig_q1.update_layout(
            title="<b>Female Representation: Visual vs Textual (%)</b>",
            xaxis_title="Year", yaxis_title="% Female Representation",
            xaxis=dict(tickmode="linear", dtick=1),
            hovermode="x unified", template="plotly_white",
            legend_title="Axis", height=420,
        )
        add_event_lines(fig_q1)
        st.plotly_chart(fig_q1, use_container_width=True)
        with st.expander("ℹ️ How to read this chart"):
            st.markdown(
                "Each line shows the **percentage of female representation** per year. "
                "The **purple line** tracks visual covers (face detection by computer vision); "
                "the **pink dashed line** tracks text articles (NLP protagonist analysis). "
                "Vertical lines mark major sporting events — look for spikes in event years "
                "and whether the two lines move together or diverge over time."
            )

    st.divider()

    # -----------------------------------------------------------------------
    # Q4 — Mega-events
    # -----------------------------------------------------------------------
    st.subheader("Q4 · Impact of Mega-Events on Female Representation")
    st.caption(
        "Compare female coverage in event years vs standard years. "
        "Select which events to include in the comparison."
    )

    q4_events = st.multiselect(
        "Events to compare",
        options=["Olympic Games", "Men's World Cup", "Women's World Cup", "UEFA Euro"],
        default=["Olympic Games", "Men's World Cup"],
        key="q4_events",
    )

    EVENT_YEAR_MAP = {
        "Olympic Games":      set(OLYMPICS.keys()),
        "Men's World Cup":    MENS_WORLD_CUPS,
        "Women's World Cup":  WOMENS_WORLD_CUPS,
        "UEFA Euro":          EURO_CUPS,
    }

    if q4_events:
        def tag_event(year):
            for ev in q4_events:
                if year in EVENT_YEAR_MAP[ev]:
                    return ev
            return "Standard Year"

        rows_q4 = []
        for axis_label, df_ax, gcol in [
            ("Text",   df_txt, "text_gender"),
            ("Visual", df_vis, "gender"),
        ]:
            yr_pct = df_ax.groupby(["year", gcol])["count"].sum().unstack(fill_value=0)
            if "Woman" not in yr_pct.columns:
                continue
            yr_pct = yr_pct.reset_index()
            yr_pct["female_pct"] = (
                yr_pct["Woman"] / (yr_pct["Woman"] + yr_pct.get("Man", 0)).replace(0, float("nan")) * 100
            )
            yr_pct["event_type"] = yr_pct["year"].apply(tag_event)
            for ev_type in q4_events + ["Standard Year"]:
                sub = yr_pct[yr_pct["event_type"] == ev_type]["female_pct"]
                if len(sub):
                    rows_q4.append({
                        "Axis": axis_label,
                        "Event Type": ev_type,
                        "Female Coverage (%)": round(sub.mean(), 2),
                    })

        if rows_q4:
            df_q4 = pd.DataFrame(rows_q4)
            color_map = {
                "Olympic Games":    "#d62728",
                "Men's World Cup":  "#ff7f0e",
                "Women's World Cup":"#e377c2",
                "UEFA Euro":        "#2ca02c",
                "Standard Year":    "#7f7f7f",
            }
            fig_q4 = px.bar(
                df_q4, x="Axis", y="Female Coverage (%)", color="Event Type",
                barmode="group", text_auto=".2f",
                color_discrete_map=color_map,
                title="<b>Female Coverage: Event Years vs Standard Years</b>",
                height=380,
            )
            fig_q4.update_traces(textfont_size=13, textposition="outside", cliponaxis=False)
            fig_q4.update_layout(template="plotly_white", title_x=0.5)
            st.plotly_chart(fig_q4, use_container_width=True)

            with st.expander("ℹ️ How to read this chart"):
                st.markdown(
                    "Each group of bars represents one news medium (text articles or visual covers). "
                    "Within each group, bars show the average female coverage percentage in years "
                    "when the selected event occurred vs years with no major event. "
                    "A taller coloured bar compared to the grey 'Standard Year' bar confirms an "
                    "'event boost' effect. If both bars are similar, the event had no editorial impact."
                )
    else:
        st.info("Select at least one event type above.")

    st.divider()

    # -----------------------------------------------------------------------
    # Q5 — Newspaper comparison
    # -----------------------------------------------------------------------
    st.subheader("Q5 · Coverage by Source")
    st.caption("Editorial comparison across news sources.")

    q5_metric = st.radio("Show", ["Heatmap", "Bar chart"], horizontal=True, key="q5_metric")
    q5_print_only = st.checkbox(
        "Restrict to A Bola, Record, O Jogo (printed dailies)", value=True, key="q5_print"
    )

    df_txt_q5 = _apply_filters(df_txt_raw)
    if q5_print_only:
        df_txt_q5 = df_txt_q5[df_txt_q5["source"].isin(PRINT_SOURCES)]

    col_v, col_t = st.columns(2)

    for col_widget, axis_label, df_ax, gcol, y_label in [
        (col_v, "Visual · Covers (%)",   df_vis,    "gender",       "Female Faces (%)"),
        (col_t, "Textual · Articles (%)", df_txt_q5, "text_gender",  "Female Articles (%)"),
    ]:
        with col_widget:
            st.markdown(f"**{axis_label}**")
            if df_ax.empty:
                st.info("No data.")
                continue

            src_col = "source"
            yr_src = df_ax.groupby(["year", src_col, gcol])["count"].sum().unstack(fill_value=0).reset_index()
            if "Woman" not in yr_src.columns:
                st.info("No female data.")
                continue

            yr_src["total"] = yr_src["Woman"] + yr_src.get("Man", 0)
            yr_src["female_pct"] = (
                yr_src["Woman"] / yr_src["total"].replace(0, float("nan")) * 100
            )
            # Suppress cells with fewer than 10 articles — percentages are not meaningful at that scale
            MIN_ARTICLES = 10
            yr_src.loc[yr_src["total"] < MIN_ARTICLES, "female_pct"] = float("nan")
            yr_src = yr_src.dropna(subset=["female_pct"])
            st.caption(f"ℹ️ Source–year combinations with fewer than {MIN_ARTICLES} articles are hidden — percentages based on very small samples are not meaningful.")

            if q5_metric == "Bar chart":
                fig5 = px.bar(
                    yr_src, x="year", y="female_pct", color=src_col,
                    barmode="group", text_auto=".1f",
                    color_discrete_map=SOURCE_COLORS,
                    labels={"female_pct": y_label, "year": "Year", src_col: "Source"},
                    height=360,
                )
                fig5.update_layout(template="plotly_white", xaxis=dict(tickmode="linear", dtick=1))
                add_event_lines(fig5, y_max=yr_src["female_pct"].max() * 1.2)
                st.plotly_chart(fig5, use_container_width=True)
                with st.expander("ℹ️ How to read this chart"):
                    st.markdown(
                        "Each bar shows the percentage of female representation for one news source in one year. "
                        "Taller bars mean more female coverage that year. "
                        "Comparing bar heights across sources in the same year reveals which outlets gave more space to women."
                    )
            else:
                pivot = yr_src.pivot_table(
                    index=src_col, columns="year", values="female_pct", aggfunc="mean"
                ).round(1)
                fig5h = go.Figure(data=go.Heatmap(
                    z=pivot.values,
                    x=[str(c) for c in pivot.columns],
                    y=pivot.index.tolist(),
                    colorscale="RdPu",
                    text=[[f"{v:.1f}%" if not np.isnan(v) else "" for v in row] for row in pivot.values],
                    texttemplate="%{text}",
                    hovertemplate="<b>%{y}</b> · %{x}<br>Female: %{z:.1f}%<extra></extra>",
                    colorbar=dict(title="Female %"),
                ))
                fig5h.update_layout(
                    xaxis_title="Year", yaxis_title="Source",
                    template="plotly_white", height=max(250, len(pivot) * 50 + 80),
                )
                st.plotly_chart(fig5h, use_container_width=True)
                with st.expander("ℹ️ How to read this chart"):
                    st.markdown(
                        "Each cell shows the average percentage of female representation for one source (row) in one year (column). "
                        "Darker pink/purple cells mean higher female coverage. "
                        "Empty or light cells indicate few or no female mentions. "
                        "Reading across a row shows how one source changed over time; reading down a column compares sources in the same year."
                    )


# ===========================================================================
# TAB 2 — Visual vs Textual, False Positives, Prominence
# ===========================================================================

with tab2:

    # -----------------------------------------------------------------------
    # Q2 — False positive filtering
    # -----------------------------------------------------------------------
    st.subheader("Q2 · Female Presence on Covers: Editorial Subject vs Peripheral Detection")
    st.caption(
        "Not all detected female faces are the editorial subject of the cover. "
        "Many are tiny incidental detections — a photo in the background, a small inset. "
        "This section separates **prominent faces** (≥ 1% of cover area, likely the featured athlete) "
        "from all detections."
    )

    if db.person_type_annotated():
        st.success(
            "✅ **Manual annotation active** — the dark bar shows only faces manually labelled as `athlete` "
            "using the annotation tool (`annotate_covers.py`)."
        )
    else:
        st.info(
            "**Proximity proxy active** — since `person_type` has not yet been annotated, "
            "the dark bar shows faces covering ≥ 1% of the cover as a proxy for editorial subjects. "
            "Run `streamlit run dashboard/annotate_covers.py` to annotate the 448 covers and get exact results."
        )

    df_fp = db.fetch_visual_fp_comparison()
    if not df_fp.empty:
        df_fp_f = df_fp[df_fp["year"].between(*year_range)].copy()
        is_annotated = (
            "annotated" in df_fp_f.columns and bool(df_fp_f["annotated"].iloc[0])
        ) if not df_fp_f.empty else db.person_type_annotated()

        # --- Stacked bar chart ---
        fig_q2 = go.Figure()

        if is_annotated:
            athlete_label   = "Athlete"
            nonsport_label  = "Publicity / other / misdetection"
            pending_label   = "Not yet annotated"
            athlete_color   = "#2ca02c"
            nonsport_color  = "#d62728"
            pending_color   = "#aec7e8"
        else:
            athlete_label   = f"Prominent (≥{_prom_threshold}% cover — likely athlete)"
            nonsport_label  = f"Peripheral (< {_prom_threshold}% cover — likely incidental)"
            pending_color   = None
            athlete_color   = "#2ca02c"
            nonsport_color  = "#d62728"

        fig_q2.add_trace(go.Bar(
            x=df_fp_f["year"], y=df_fp_f["count_athlete"],
            name=athlete_label, marker_color=athlete_color,
            hovertemplate="<b>%{x}</b><br>" + athlete_label + ": %{y}<extra></extra>",
        ))
        fig_q2.add_trace(go.Bar(
            x=df_fp_f["year"], y=df_fp_f["count_non_sport"],
            name=nonsport_label, marker_color=nonsport_color,
            hovertemplate="<b>%{x}</b><br>" + nonsport_label + ": %{y}<extra></extra>",
        ))
        if is_annotated and df_fp_f["count_unannotated"].sum() > 0:
            fig_q2.add_trace(go.Bar(
                x=df_fp_f["year"], y=df_fp_f["count_unannotated"],
                name=pending_label, marker_color=pending_color,
                hovertemplate="<b>%{x}</b><br>Pending: %{y}<extra></extra>",
            ))

        fig_q2.update_layout(
            title="<b>Female Face Detections by Category per Year</b>",
            xaxis_title="Year", yaxis_title="Female Face Detections",
            barmode="stack", template="plotly_white", title_x=0.5,
            xaxis=dict(tickmode="linear", dtick=1),
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
            height=420,
        )
        add_event_lines(fig_q2)
        st.plotly_chart(fig_q2, use_container_width=True)

        with st.expander("ℹ️ How to read this chart"):
            if is_annotated:
                st.markdown(
                    "Each bar is split into up to three segments: **green** = faces manually labelled as athletes; "
                    "**red** = faces labelled as publicity, fans, background figures, or misdetections; "
                    "**blue** = not yet annotated. "
                    "The total bar height equals all female face detections that year. "
                    "A tall green segment means women appeared on covers primarily as athletes."
                )
            else:
                st.markdown(
                    "Each bar is split by face size as a proxy: **green** = faces covering ≥ 1% of the cover "
                    "(likely the editorial subject); **red** = smaller, peripheral detections. "
                    "Run the annotation tool (`annotate_covers.py`) to replace this proxy with real labels."
                )

        # --- Summary metrics ---
        total_athlete   = int(df_fp_f["count_athlete"].sum())
        total_nonsport  = int(df_fp_f["count_non_sport"].sum())
        total_pending   = int(df_fp_f["count_unannotated"].sum())
        total_all       = total_athlete + total_nonsport + total_pending

        mc1, mc2, mc3 = st.columns(3)
        mc1.metric("Athletes detected", total_athlete,
                   delta=f"{round(total_athlete/total_all*100,1)}% of total" if total_all else None)
        mc2.metric("Publicity / other", total_nonsport,
                   delta=f"{round(total_nonsport/total_all*100,1)}% of total" if total_all else None,
                   delta_color="inverse")
        mc3.metric("Total female detections", total_all)

        # --- Per-year table ---
        st.markdown("**Breakdown per year**")
        col_map = {
            "year": "Year",
            "count_athlete": "Athletes" if is_annotated else f"Prominent (≥{_prom_threshold}%)",
            "count_non_sport": "Publicity / Other" if is_annotated else "Peripheral",
            "count_unannotated": "Pending",
        }
        df_table = df_fp_f[list(col_map.keys())].rename(columns=col_map).set_index("Year")
        if not is_annotated:
            df_table = df_table.drop(columns=["Pending"], errors="ignore")
        df_table["Athlete rate (%)"] = (
            df_table.iloc[:, 0] /
            df_table.iloc[:, :2].sum(axis=1).replace(0, float("nan")) * 100
        ).round(1)
        st.dataframe(
            df_table.style.background_gradient(subset=["Athlete rate (%)"], cmap="Greens"),
            use_container_width=True,
        )
    else:
        st.info("No cover data found in the database.")

    st.divider()

    # -----------------------------------------------------------------------
    # Q3 — Visual vs Textual correlation
    # -----------------------------------------------------------------------
    st.subheader("Q3 · Visual Axis vs Textual Axis: Do Covers Reflect Articles?")

    st.info(
        "**How to read this:** Each dot is one year. The horizontal axis shows the percentage of "
        "**female faces on covers**; the vertical axis shows the percentage of **female-dominant articles**. "
        "If both axes moved together, the dots would align along an upward diagonal. "
        "A flat or downward pattern means covers and articles tell different stories about women."
    )

    if df_corr.empty:
        st.info("Insufficient data for correlation (years must overlap between both collections).")
    else:
        x_vals = df_corr["visual_female_pct"].values
        y_vals = df_corr["text_female_pct"].values
        m, b   = np.polyfit(x_vals, y_vals, 1)
        x_line = np.linspace(x_vals.min(), x_vals.max(), 100)

        from scipy import stats as _stats
        r_val, p_val = _stats.pearsonr(x_vals, y_vals)

        fig_q3 = go.Figure()
        fig_q3.add_trace(go.Scatter(
            x=x_vals, y=y_vals,
            mode="markers+text",
            text=df_corr["year"].astype(str),
            textposition="top center",
            marker=dict(size=11, color="#9467bd",
                        line=dict(color="white", width=1)),
            name="Years",
            hovertemplate="<b>%{text}</b><br>Covers: %{x:.1f}%<br>Articles: %{y:.1f}%<extra></extra>",
        ))
        fig_q3.add_trace(go.Scatter(
            x=x_line, y=m * x_line + b,
            mode="lines",
            line=dict(color="#ff7f0e", dash="dash", width=2),
            name=f"Trend (r = {r_val:.2f}, p = {p_val:.3f})",
        ))
        fig_q3.update_layout(
            title="<b>Correlation: Female Faces on Covers vs Female-Dominant Articles</b>",
            xaxis_title="Female Faces on Covers (%)",
            yaxis_title="Female-Dominant Articles (%)",
            template="plotly_white", title_x=0.5, height=430,
        )
        st.plotly_chart(fig_q3, use_container_width=True)

        col_r, col_interp = st.columns([1, 3])
        col_r.metric("Pearson r", f"{r_val:.3f}",
                     help="Range: -1 (perfect negative) to +1 (perfect positive). 0 = no linear relation.")
        with col_interp:
            if abs(r_val) < 0.2:
                st.warning("**Weak or no correlation** — covers and articles are editorially independent.")
            elif r_val > 0:
                st.success(f"**Positive correlation (r={r_val:.2f})** — when women appear more on covers, "
                           "they also feature more in articles.")
            else:
                st.error(f"**Negative correlation (r={r_val:.2f})** — covers overrepresent women "
                         "relative to articles, or vice versa.")

        # Simple gap chart — easier to read for non-technical audience
        df_gap = df_corr.copy()
        df_gap["gap"] = (df_gap["visual_female_pct"] - df_gap["text_female_pct"]).round(2)
        fig_gap = go.Figure()
        fig_gap.add_trace(go.Bar(
            x=df_gap["year"], y=df_gap["gap"],
            marker_color=["#9467bd" if g >= 0 else "#e377c2" for g in df_gap["gap"]],
            text=df_gap["gap"].apply(lambda v: f"{v:+.1f} pp"),
            textposition="outside",
            hovertemplate="<b>%{x}</b><br>Gap: %{y:+.1f} pp<extra></extra>",
        ))
        fig_gap.add_hline(y=0, line_dash="dash", line_color="grey")
        fig_gap.update_layout(
            title="<b>Annual Gap: Covers % minus Articles % (percentage points)</b><br>"
                  "<sup>Purple bars = covers show MORE women than articles. "
                  "Pink bars = articles show MORE women than covers.</sup>",
            xaxis_title="Year", yaxis_title="Gap (pp)",
            template="plotly_white", title_x=0.5,
            xaxis=dict(tickmode="linear", dtick=1), height=320,
        )
        st.plotly_chart(fig_gap, use_container_width=True)
        with st.expander("ℹ️ How to read this chart"):
            st.markdown(
                "Each bar shows how many **percentage points** the visual axis is ahead of (or behind) the textual axis. "
                "A **purple bar above zero** means covers featured proportionally more women than articles did. "
                "A **pink bar below zero** means articles mentioned more women than were visible on covers. "
                "Years near zero indicate editorial consistency between visual and textual channels."
            )

    st.divider()

    # -----------------------------------------------------------------------
    # Q6 — Visual prominence
    # -----------------------------------------------------------------------
    st.subheader("Q6 · Visual Prominence — Space Occupied on the Cover")

    st.info(
        "**How to read this:** The prominence ratio compares the average cover area "
        "(bounding box size as % of the page) occupied by female faces vs male faces. "
        "A value of **1.0 = perfect parity** — both genders occupy the same space on average. "
        "Values **below 1.0** mean women appear smaller on the page even when they are present. "
        "Values **above 1.0** mean women occupy more space — rare, and often linked to Olympic covers."
    )

    if df_prom.empty:
        st.info("No prominence data for the selected period.")
    else:
        prom_yr = df_prom.groupby(["year", "gender"]).agg(
            avg_prominence=("avg_prominence", "mean"),
            total=("count", "sum"),
        ).reset_index()

        fig_prom = px.bar(
            prom_yr, x="year", y="avg_prominence", color="gender", barmode="group",
            text_auto=".2f",
            color_discrete_map={"Man": "#1f77b4", "Woman": "#e377c2"},
            labels={"avg_prominence": "Avg Area on Cover (%)", "year": "Year", "gender": "Gender"},
            title="<b>Average Cover Area Occupied by Gender (%)</b>",
            height=360,
        )
        fig_prom.update_layout(template="plotly_white", title_x=0.5,
                               xaxis=dict(tickmode="linear", dtick=1))
        add_event_lines(fig_prom)
        st.plotly_chart(fig_prom, use_container_width=True)
        with st.expander("ℹ️ How to read this chart"):
            st.markdown(
                "Each bar shows the **average percentage of the cover page** occupied by faces of that gender. "
                "A higher bar means those faces appeared larger on the page. "
                "If the female bar is consistently shorter than the male bar, women appear smaller even when present — "
                "a form of visual marginalisation independent of raw count."
            )

        ratio_df = prom_yr.pivot(index="year", columns="gender", values="avg_prominence").reset_index()
        if "Woman" in ratio_df.columns and "Man" in ratio_df.columns:
            ratio_df["ratio_w_m"] = (ratio_df["Woman"] / ratio_df["Man"].replace(0, float("nan"))).round(3)
            fig_ratio = px.line(
                ratio_df, x="year", y="ratio_w_m", markers=True,
                labels={"ratio_w_m": "Ratio Area Woman / Man", "year": "Year"},
                title="<b>Prominence Ratio: Female Area / Male Area (1.0 = parity)</b>",
                color_discrete_sequence=["#ff7f0e"], height=300,
            )
            fig_ratio.add_hline(y=1.0, line_dash="dash", line_color="grey",
                                annotation_text="Parity", annotation_position="right")
            fig_ratio.update_layout(template="plotly_white", title_x=0.5,
                                    xaxis=dict(tickmode="linear", dtick=1))
            add_event_lines(fig_ratio)
            st.plotly_chart(fig_ratio, use_container_width=True)
            with st.expander("ℹ️ How to read this chart"):
                st.markdown(
                    "The line shows the ratio of **average female cover area ÷ average male cover area** per year. "
                    "A value of **1.0** (grey dashed line) means perfect parity. "
                    "Values **below 1.0** mean women occupy less page space than men on average. "
                    "Values **above 1.0** — rare — mean women appear larger. "
                    "Peaks often coincide with the Olympics when female athletes dominate cover photography."
                )


# ===========================================================================
# TAB 3 — Diversity, disciplines, semantic context
# ===========================================================================

with tab3:

    # -----------------------------------------------------------------------
    # Q8 — Protagonist diversity
    # -----------------------------------------------------------------------
    st.subheader("Q8 · Protagonist Diversity: Star Concentration or Genuine Coverage?")
    st.caption(
        "Do 100 mentions mean 100 different athletes, or just the same athlete 100 times? "
        "The HHI index measures concentration: 0 = perfect diversity · 1 = total monopoly."
    )

    if df_ent_dist.empty:
        st.info("No named female entities in the database.")
    else:
        total_mentions = int(df_ent_dist["count"].sum())
        n_unique       = len(df_ent_dist)
        shares         = df_ent_dist["count"] / total_mentions
        hhi            = float((shares ** 2).sum())
        hhi_norm       = round((hhi - 1/n_unique) / (1 - 1/n_unique), 4) if n_unique > 1 else 1.0
        avg_per_ent    = round(total_mentions / n_unique, 1) if n_unique else 0

        kc1, kc2, kc3, kc4 = st.columns(4)
        kc1.metric("Total Mentions",         f"{total_mentions:,}")
        kc2.metric("Unique Protagonists",    f"{n_unique:,}")
        kc3.metric("Avg Mentions / Athlete", f"{avg_per_ent}")
        kc4.metric("HHI (normalised)",       f"{hhi_norm:.3f}",
                   help="0 = max diversity · 1 = single athlete monopoly")

        if hhi_norm > 0.5:
            st.error("🔴 **High concentration** — coverage focuses on very few star athletes.")
        elif hhi_norm > 0.15:
            st.warning("🟡 **Moderate concentration** — some diversity, but a few athletes dominate.")
        else:
            st.success("🟢 **Good diversity** — mentions are spread across many athletes.")

        col_left, col_right = st.columns(2)

        with col_left:
            top15 = df_ent_dist.head(15)
            fig_ner = px.bar(
                top15.sort_values("count"), x="count", y="entity",
                orientation="h", text_auto=True,
                labels={"count": "Mentions", "entity": "Athlete / Protagonist"},
                title="<b>Top 15 Female Protagonists (NER · WikiNeural)</b>",
                color="count", color_continuous_scale="PuRd",
                height=460,
            )
            fig_ner.update_layout(template="plotly_white", showlegend=False,
                                  coloraxis_showscale=False)
            st.plotly_chart(fig_ner, use_container_width=True)
            with st.expander("ℹ️ How to read this chart"):
                st.markdown(
                    "Each bar shows the total number of articles in which that athlete appears as a protagonist, "
                    "across all selected years and sources. "
                    "Longer bar = more mentions. "
                    "A very long top bar compared to the rest signals a 'star effect' where one athlete dominates coverage."
                )

        with col_right:
            df_rank = df_ent_dist.reset_index(drop=True)
            df_rank["rank"] = df_rank.index + 1
            fig_zipf = go.Figure()
            fig_zipf.add_trace(go.Scatter(
                x=df_rank["rank"], y=df_rank["count"],
                mode="lines+markers",
                line=dict(color="#e377c2", width=2), marker=dict(size=5),
                hovertemplate="Rank %{x}: <b>%{customdata}</b><br>Mentions: %{y}<extra></extra>",
                customdata=df_rank["entity"],
            ))
            fig_zipf.update_layout(
                title="<b>Rank–Frequency Distribution</b><br>"
                      "<sup>Steep curve = star dependency · Gradual curve = diversity</sup>",
                xaxis_title="Athlete rank", yaxis_title="Mentions",
                template="plotly_white", title_x=0.5, height=460,
            )
            st.plotly_chart(fig_zipf, use_container_width=True)
            with st.expander("ℹ️ How to read this chart"):
                st.markdown(
                    "Athletes are ranked from most mentioned (rank 1) to least mentioned. "
                    "A **steep drop** at the left means the top 1–2 athletes absorb most mentions — high star dependency. "
                    "A **gradual slope** means coverage is more evenly spread across many athletes — higher diversity. "
                    "Hover over each point to see the athlete's name and mention count."
                )

        # ---- Athlete detail explorer ----
        st.divider()
        st.markdown("#### 🔎 Athlete Detail Explorer")
        st.caption("Select an athlete to see her coverage profile and Wikidata information.")

        athlete_options = df_ent_dist["entity"].tolist()
        selected_athlete = st.selectbox(
            "Select an athlete", options=athlete_options, key="q8_athlete"
        )

        if selected_athlete:
            with st.spinner(f"Loading details for {selected_athlete}…"):
                df_ath = db.fetch_athlete_articles(selected_athlete, "feminine")

            if df_ath.empty:
                st.info("No articles found for this athlete.")
            else:
                col_a, col_b, col_c = st.columns(3)
                yr_counts = df_ath["year"].value_counts()
                top_year  = int(yr_counts.idxmax()) if not yr_counts.empty else "N/A"
                top_src   = df_ath["source"].value_counts().idxmax() if not df_ath["source"].empty else "N/A"
                col_a.metric("Total Articles",      len(df_ath))
                col_b.metric("Year of Most Coverage", top_year)
                col_c.metric("Top Source",           top_src)

                # Year chart
                df_ath_yr = yr_counts.sort_index().reset_index()
                df_ath_yr.columns = ["Year", "Articles"]
                fig_ath = px.bar(
                    df_ath_yr, x="Year", y="Articles",
                    title=f"<b>{selected_athlete} — Articles per Year</b>",
                    color_discrete_sequence=["#e377c2"],
                )
                fig_ath.update_layout(template="plotly_white", height=250,
                                      xaxis=dict(tickmode="linear", dtick=1))
                st.plotly_chart(fig_ath, use_container_width=True)
                with st.expander("ℹ️ How to read this chart"):
                    st.markdown(
                        "Each bar shows how many articles mentioned this athlete as a protagonist in that year. "
                        "Peak years usually coincide with major competitions or personal milestones. "
                        "Years with no bar mean the athlete was not detected as a protagonist in any article that year."
                    )

                # YAKE keywords for this athlete (filtering out the athlete's name tokens)
                all_text = " ".join(df_ath["content"].dropna().tolist())
                name_tokens = [t.lower() for t in selected_athlete.split() if len(t) > 2]
                if len(all_text) > 100:
                    kw_ext = yake.KeywordExtractor(lan="pt", n=2, dedupLim=0.8, top=10)
                    raw_kws = kw_ext.extract_keywords(all_text)
                    kws_clean = [
                        kw for kw, _ in raw_kws
                        if not any(tok in kw.lower() for tok in name_tokens)
                    ]
                    if kws_clean:
                        st.markdown(f"**Top keywords in articles about {selected_athlete}:**  \n"
                                    + "  ·  ".join(f"`{k}`" for k in kws_clean[:8]))

                # Wikidata info
                try:
                    sys.path.insert(0, os.path.abspath(
                        os.path.join(os.path.dirname(__file__), "..", "src", "utils")
                    ))
                    from wikidata_api import consultar_wikidata_info_completa
                    with st.spinner("Fetching Wikidata info…"):
                        wd = consultar_wikidata_info_completa(selected_athlete)
                    wd_cols = st.columns(4)
                    wd_cols[0].metric("Gender",      wd.get("gender")      or "Unknown")
                    wd_cols[1].metric("Sport",       wd.get("sport")       or "Unknown")
                    wd_cols[2].metric("Nationality", wd.get("nationality") or "Unknown")
                    wd_cols[3].metric("Birth Year",  str(wd.get("birth_year") or "Unknown"))
                except Exception:
                    pass

    st.divider()

    # -----------------------------------------------------------------------
    # Q7 — Sport disciplines
    # -----------------------------------------------------------------------
    st.subheader("Q7 · Sports Disciplines Driving Female Representation")
    st.caption(
        "Keyword-based detection of sport discipline in female-dominant articles. "
        "Select a specific discipline to drill down."
    )

    q7_tab_overview, q7_tab_drill = st.tabs(["Overview", "Discipline drill-down"])

    with q7_tab_overview:
        if df_sports.empty:
            st.info("No female articles detected for discipline analysis.")
        else:
            col_sp1, col_sp2 = st.columns([2, 3])

            with col_sp1:
                df_sports_display = df_sports[df_sports["sport"] != "Other"].copy() \
                    if "Other" in df_sports["sport"].values else df_sports.copy()
                fig_sp = px.bar(
                    df_sports_display.head(12).sort_values("count"),
                    x="count", y="sport", orientation="h", text_auto=True,
                    labels={"count": "Female Articles", "sport": "Discipline"},
                    title="<b>Disciplines with Most Female Coverage</b>",
                    color="count", color_continuous_scale="Teal",
                    height=420,
                )
                fig_sp.update_layout(template="plotly_white", showlegend=False,
                                     coloraxis_showscale=False)
                st.plotly_chart(fig_sp, use_container_width=True)
                with st.expander("ℹ️ How to read this chart"):
                    st.markdown(
                        "Each bar shows the total number of female-dominant articles linked to that discipline, "
                        "detected by sport-specific keywords across all selected years. "
                        "Longer bars mean more coverage. "
                        "Disciplines without their own bar were either absent or classified as 'Other'."
                    )

                if "Other" in df_sports["sport"].values:
                    n_other = int(df_sports[df_sports["sport"] == "Other"]["count"].sum())
                    st.info(
                        f"**{n_other} articles** were not matched to any discipline keyword. "
                        "These may cover multi-sport events, opinion pieces, or disciplines "
                        "not yet in the keyword list. Expand keywords in `db.py > SPORT_KEYWORDS` "
                        "to reduce this category."
                    )

            with col_sp2:
                if not df_sports_yr.empty:
                    top8 = df_sports[df_sports["sport"] != "Other"].head(8)["sport"].tolist()
                    df_hm = df_sports_yr[df_sports_yr["sport"].isin(top8)].copy()
                    if not df_hm.empty:
                        pivot = df_hm.pivot_table(
                            index="sport", columns="year",
                            values="count", aggfunc="sum", fill_value=0,
                        )
                        pivot.columns = [int(c) for c in pivot.columns]
                        pivot = pivot[[c for c in pivot.columns
                                       if year_range[0] <= c <= year_range[1]]]
                        fig_hm = px.imshow(
                            pivot, color_continuous_scale="Teal", aspect="auto",
                            title="<b>Female Coverage by Discipline and Year</b>",
                            labels=dict(x="Year", y="Discipline", color="Articles"),
                            text_auto=True, height=420,
                        )
                        fig_hm.update_layout(template="plotly_white", title_x=0.5)
                        st.plotly_chart(fig_hm, use_container_width=True)
                        with st.expander("ℹ️ How to read this chart"):
                            st.markdown(
                                "Each cell shows the number of female-dominant articles for a discipline (row) in a year (column). "
                                "Darker teal = more articles. White/empty = none detected. "
                                "Reading across a row shows how one sport's female coverage evolved over time; "
                                "reading down a column shows which disciplines drove female coverage in a specific year."
                            )

    with q7_tab_drill:
        disciplines = sorted(db.SPORT_KEYWORDS.keys())
        sel_disc = st.selectbox("Select discipline", disciplines, key="q7_disc")
        sel_disc_yr = st.slider(
            "Year range", 1998, 2024, year_range, key="q7_yr"
        )

        if sel_disc and not df_sports_yr.empty:
            disc_data = df_sports_yr[
                (df_sports_yr["sport"] == sel_disc) &
                (df_sports_yr["year"].astype(int).between(*sel_disc_yr))
            ].sort_values("year")

            if disc_data.empty:
                st.info(f"No female coverage detected for **{sel_disc}** in this period.")
            else:
                disc_data = disc_data.copy()
                disc_data["year"] = disc_data["year"].astype(int)
                all_years_range = list(range(sel_disc_yr[0], sel_disc_yr[1] + 1))
                disc_data = (
                    disc_data[["year", "count"]]
                    .set_index("year")
                    .reindex(all_years_range, fill_value=0)
                    .reset_index()
                    .rename(columns={"index": "year"})
                )

                fig_dd = px.bar(
                    disc_data, x="year", y="count",
                    title=f"<b>{sel_disc} — Female Coverage per Year</b>",
                    labels={"year": "Year", "count": "Female Articles"},
                    color_discrete_sequence=["#17becf"],
                )
                add_event_lines(fig_dd, y_max=max(disc_data["count"].max() * 1.2, 1))
                fig_dd.update_layout(template="plotly_white", title_x=0.5,
                                     xaxis=dict(tickmode="linear", dtick=1),
                                     bargap=0.3)
                st.plotly_chart(fig_dd, use_container_width=True)
                with st.expander("ℹ️ How to read this chart"):
                    st.markdown(
                        "Each bar shows how many female-dominant articles mentioned this discipline in that year. "
                        "Years with no bar had zero detected articles for this sport. "
                        "Vertical lines mark major events — peaks that coincide with event lines confirm the competition drove coverage."
                    )

                peak_yr = int(disc_data.loc[disc_data["count"].idxmax(), "year"])
                st.metric(f"Peak year for {sel_disc}", peak_yr,
                          help="Year with most female articles mentioning this discipline.")

        st.markdown("**Active keywords for this discipline:**")
        st.write("  ·  ".join(f"`{k}`" for k in db.SPORT_KEYWORDS.get(sel_disc, [])))

    st.divider()

    # -----------------------------------------------------------------------
    # Q9 — Semantic analysis
    # -----------------------------------------------------------------------
    st.subheader("Q9 · Semantic Context: Athletic Performance or Personal Sphere?")

    q9_tab_frame, q9_tab_kw, q9_tab_prot = st.tabs([
        "A · Framing", "B · Global Keywords", "C · Protagonist Keywords"
    ])

    # Expanded framing keyword dictionaries
    FRAMING_DICT = {
        "Performance": [
            "vitória", "vitoria", "derrota", "golo", "golos", "medalha", "recorde",
            "competição", "competicao", "título", "titulo", "campeonato", "torneio",
            "treino", "atleta", "desempenho", "marca", "prova", "final", "semifinal",
            "eliminatória", "qualificação", "pódio", "podio", "ouro", "prata", "bronze",
            "classificação", "resultado", "sprint", "maratona", "set", "match", "ganha",
            "venceu", "perdeu", "empate", "hat-trick", "recorde mundial", "campeã",
            "medalha de ouro", "primeira classificada", "apurou", "passou", "eliminou",
            "conquistou", "vencedora", "tricampeã",
        ],
        "Personal": [
            "casamento", "noivado", "namorado", "namorada", "família", "familia",
            "filho", "filha", "gravidez", "grávida", "maternidade", "moda", "beleza",
            "escândalo", "escandalo", "polém", "vida privada", "relacionamento",
            "separação", "separacao", "divórcio", "divorcio", "festa", "rede social",
            "instagram", "bikini", "biquíni", "fotografia", "foto", "sexy",
            "romance", "namoro", "companheiro", "companheira", "marido", "esposa",
            "mãe", "pai", "criança", "bebé", "bebe", "gravidez",
        ],
        "Institutional": [
            "presidente", "presidenta", "dirigente", "árbitro", "arbitro", "árbitras",
            "federação", "federacao", "comité", "comite", "gestão", "gestao",
            "administração", "administracao", "cargo", "eleição", "eleicao",
            "comissão", "comissao", "diretora", "coordenadora", "treinadora",
            "selecionadora", "técnica", "tecnica", "associação", "associacao",
        ],
    }

    def classify_framing(text):
        t = str(text).lower()
        scores = {cat: sum(1 for kw in kws if kw in t)
                  for cat, kws in FRAMING_DICT.items()}
        total  = sum(scores.values())
        if total == 0:
            return "Undetermined", 0.0
        winner = max(scores, key=scores.get)
        confidence = round(scores[winner] / total, 2)
        # Require at least 2 matching keywords for a definitive classification
        if scores[winner] < 2:
            return "Undetermined", confidence
        return winner, confidence

    with q9_tab_frame:
        st.caption(
            "Articles are classified into framing categories using an expanded keyword dictionary. "
            "A minimum of 2 matched keywords is required to avoid spurious classifications."
        )

        if df_sem.empty:
            st.info("No female articles available for framing analysis.")
        else:
            @st.cache_data(ttl=600, show_spinner=False)
            def _run_framing(texts_tuple):
                results = [classify_framing(t) for t in texts_tuple]
                frames  = [r[0] for r in results]
                confs   = [r[1] for r in results]
                return frames, confs

            texts_tuple = tuple(df_sem["text"].dropna().tolist())
            frames, confs = _run_framing(texts_tuple)

            df_fr = pd.DataFrame({"frame": frames, "confidence": confs})
            overall = df_fr["frame"].value_counts(normalize=True) * 100

            col_fr1, col_fr2 = st.columns(2)
            with col_fr1:
                fig_fr = px.pie(
                    overall.reset_index().rename(columns={"proportion": "Share", "frame": "Frame"}),
                    names="Frame", values="Share",
                    title="<b>Overall Framing Distribution (Female Articles)</b>",
                    color_discrete_map={
                        "Performance": "#2ca02c", "Personal": "#d62728",
                        "Institutional": "#1f77b4", "Undetermined": "#aec7e8",
                    },
                    hole=0.4,
                )
                fig_fr.update_layout(template="plotly_white")
                st.plotly_chart(fig_fr, use_container_width=True)
                with st.expander("ℹ️ How to read this chart"):
                    st.markdown(
                        "Each slice shows what share of female-dominant articles falls into a framing category, "
                        "classified by keyword matching (minimum 2 keywords required). "
                        "A large **green (Performance)** slice means coverage focuses on athletic achievements. "
                        "A large **red (Personal)** slice means coverage focuses on private life and appearance. "
                        "A large **grey (Undetermined)** slice means many articles were too short or ambiguous to classify."
                    )

            with col_fr2:
                st.markdown("**What each category means:**")
                st.markdown("""
- 🟢 **Performance** — victory, defeat, records, competitions, titles
- 🔴 **Personal** — family, relationships, appearance, private life
- 🔵 **Institutional** — federation, management, coaching, refereeing
- ⚪ **Undetermined** — fewer than 2 keyword matches in any category
""")
                if "Performance" in overall.index and "Personal" in overall.index:
                    ratio = overall["Performance"] / max(overall.get("Personal", 0.01), 0.01)
                    if ratio > 3:
                        st.success(f"Performance coverage dominates ({ratio:.1f}× more than personal).")
                    elif ratio > 1:
                        st.info(f"Performance leads but personal coverage is present (ratio {ratio:.1f}×).")
                    else:
                        st.warning("Personal coverage equals or exceeds performance coverage.")

    with q9_tab_kw:
        st.caption("Top keywords extracted via YAKE! from all female-dominant articles.")

        @st.cache_data(ttl=600, show_spinner=False)
        def _run_yake(texts_tuple, top_n=35):
            if not texts_tuple:
                return pd.DataFrame(columns=["keyword", "score"])
            kw_ext  = yake.KeywordExtractor(lan="pt", n=2, dedupLim=0.8, top=top_n)
            combined = " ".join(t for t in texts_tuple if isinstance(t, str) and len(t) > 10)
            if len(combined) < 50:
                return pd.DataFrame(columns=["keyword", "score"])
            raw = kw_ext.extract_keywords(combined)
            df_kw = pd.DataFrame(raw, columns=["keyword", "score"])
            df_kw["relevance"] = 1 - df_kw["score"]
            return df_kw.sort_values("relevance", ascending=False)

        if df_sem.empty:
            st.info("No female articles for keyword extraction.")
        else:
            texts_tuple_kw = tuple(df_sem["text"].dropna().tolist())
            with st.spinner("Extracting keywords with YAKE!…"):
                df_kw = _run_yake(texts_tuple_kw)

            if df_kw.empty:
                st.info("Insufficient text for keyword extraction.")
            else:
                fig_kw = px.bar(
                    df_kw.head(25).sort_values("relevance"),
                    x="relevance", y="keyword", orientation="h", text_auto=".3f",
                    labels={"relevance": "Relevance (1 − YAKE score)", "keyword": "Keyword"},
                    title="<b>Top 25 Keywords in Female-Dominant Articles</b>",
                    color="relevance", color_continuous_scale="Magenta",
                    height=600,
                )
                fig_kw.update_layout(template="plotly_white", showlegend=False,
                                     coloraxis_showscale=False)
                st.plotly_chart(fig_kw, use_container_width=True)
                with st.expander("ℹ️ How to read this chart"):
                    st.markdown(
                        "Keywords are extracted automatically from all female-dominant articles using the YAKE! algorithm "
                        "(no training data required). "
                        "**Relevance** is computed as 1 minus the YAKE score — higher = more distinctive to this corpus. "
                        "Longer bars indicate terms that appear frequently and are specific to articles about female athletes. "
                        "Generic stopwords are filtered out automatically."
                    )

                with st.expander("Full keyword table"):
                    st.dataframe(df_kw, use_container_width=True, hide_index=True)

    with q9_tab_prot:
        st.caption(
            "Choose a year and a protagonist to see the keywords from articles mentioning her. "
            "The athlete's own name tokens are automatically removed from the keywords."
        )

        all_years_txt = sorted(df_txt_raw["source"].drop_duplicates().tolist()) \
            if not df_txt_raw.empty else []

        # Fetch top 3 female + top 3 male protagonists per year
        @st.cache_data(ttl=600, show_spinner=False)
        def _get_top_protagonists_by_year(top_n=3):
            db_conn = db.get_db()
            result = {}
            for gender_key, label in [("feminine", "female"), ("masculine", "male")]:
                field = f"gender_analysis.details.protagonists.{gender_key}"
                pipeline = [
                    {"$unwind": f"${field}"},
                    {"$group": {"_id": {"year": "$year", "entity": f"${field}"},
                                "count": {"$sum": 1}}},
                    {"$sort": {"_id.year": 1, "count": -1}},
                    {"$group": {"_id": "$_id.year",
                                "entities": {"$push": "$_id.entity"},
                                "counts": {"$push": "$count"}}},
                ]
                for r in db_conn["articles_final"].aggregate(pipeline):
                    yr = r["_id"]
                    if yr not in result:
                        result[yr] = {"female": [], "male": []}
                    result[yr][label] = list(zip(r["entities"][:top_n], r["counts"][:top_n]))
            return result

        with st.spinner("Loading protagonist data…"):
            yr_top = _get_top_protagonists_by_year()

        available_years = sorted(yr_top.keys())
        if not available_years:
            st.info("No protagonist data found in the database.")
        else:
            sel_yr_c = st.selectbox("Select year", available_years,
                                    index=len(available_years) - 1, key="q9c_year")

            year_data   = yr_top.get(sel_yr_c, {"female": [], "male": []})
            female_top3 = year_data.get("female", [])
            male_top3   = year_data.get("male", [])

            col_f, col_m = st.columns(2)
            with col_f:
                st.markdown("**Top 3 Female Protagonists**")
                for name, cnt in female_top3:
                    st.markdown(f"- **{name}** ({cnt} mentions)")
            with col_m:
                st.markdown("**Top 3 Male Protagonists**")
                for name, cnt in male_top3:
                    st.markdown(f"- **{name}** ({cnt} mentions)")

            all_top3 = [(n, "feminine") for n, _ in female_top3] + [(n, "masculine") for n, _ in male_top3]
            if not all_top3:
                st.info(f"No protagonists recorded for {sel_yr_c}.")
            else:
                prot_labels = [f"{n} ({'F' if g == 'feminine' else 'M'})" for n, g in all_top3]
                sel_idx = st.selectbox("Select protagonist to explore",
                                       options=range(len(prot_labels)),
                                       format_func=lambda i: prot_labels[i],
                                       key="q9c_prot")

                sel_prot, sel_gender_key = all_top3[sel_idx]

                with st.spinner(f"Loading profile for {sel_prot}..."):
                    df_prot = db.fetch_athlete_articles(sel_prot, sel_gender_key)

                if df_prot.empty:
                    st.info(f"No articles found for {sel_prot}.")
                else:
                    yr_counts_p = df_prot["year"].value_counts()
                    top_year_p  = int(yr_counts_p.idxmax()) if not yr_counts_p.empty else "N/A"
                    top_src_p   = df_prot["source"].value_counts().idxmax() if not df_prot["source"].empty else "N/A"

                    col_pa, col_pb, col_pc = st.columns(3)
                    col_pa.metric("Total Articles",        len(df_prot))
                    col_pb.metric("Year of Most Coverage", top_year_p)
                    col_pc.metric("Top Source",            top_src_p)

                    df_prot_chart = yr_counts_p.sort_index().reset_index()
                    df_prot_chart.columns = ["Year", "Articles"]
                    fig_prot = px.bar(
                        df_prot_chart, x="Year", y="Articles",
                        title=f"<b>{sel_prot} — Articles per Year</b>",
                        color_discrete_sequence=["#9467bd"],
                    )
                    fig_prot.update_layout(template="plotly_white", height=250,
                                           xaxis=dict(tickmode="linear", dtick=1))
                    st.plotly_chart(fig_prot, use_container_width=True)
                    with st.expander("ℹ️ How to read this chart"):
                        st.markdown(
                            "Each bar shows how many articles mentioned this protagonist across all years in the database. "
                            "The selected year (above) was used only to identify the top 3 protagonists — "
                            "the chart shows the full career timeline, not just that year. "
                            "Peak bars often indicate championship seasons or high-profile media moments."
                        )

                    all_text_p  = " ".join(df_prot["content"].dropna().tolist())
                    name_tokens = [t.lower() for t in sel_prot.split() if len(t) > 2]
                    if len(all_text_p) > 100:
                        kw_ext_p = yake.KeywordExtractor(lan="pt", n=2, dedupLim=0.8, top=15)
                        raw_p    = kw_ext_p.extract_keywords(all_text_p)
                        kws_p    = [kw for kw, _ in raw_p
                                    if not any(tok in kw.lower() for tok in name_tokens)]
                        if kws_p:
                            st.markdown(f"**Top keywords in articles about {sel_prot}:**  \n"
                                        + "  .  ".join(f"`{k}`" for k in kws_p[:8]))

                    try:
                        from wikidata_api import consultar_wikidata_info_completa
                        with st.spinner("Fetching Wikidata info..."):
                            wd_p = consultar_wikidata_info_completa(sel_prot)
                        wd_pc = st.columns(4)
                        wd_pc[0].metric("Gender",      wd_p.get("gender")      or "Unknown")
                        wd_pc[1].metric("Sport",       wd_p.get("sport")       or "Unknown")
                        wd_pc[2].metric("Nationality", wd_p.get("nationality") or "Unknown")
                        wd_pc[3].metric("Birth Year",  str(wd_p.get("birth_year") or "Unknown"))
                    except Exception:
                        pass

    st.divider()

    # -----------------------------------------------------------------------
    # Pipeline statistics
    # -----------------------------------------------------------------------
    st.subheader("📊 Pipeline Status")
    with st.spinner("Computing pipeline statistics…"):
        stats = db.fetch_pipeline_stats()

    s1, s2, s3, s4 = st.columns(4)
    s1.metric("Classification Rate (Text)", f"{stats['classification_rate_pct']}%")
    s2.metric("Faces — High Confidence (≥0.90)", f"{stats['high_conf_rate_pct']}%")
    s3.metric("Unique Female Entities (NER)", f"{stats['unique_feminine_entities']:,}")
    s4.metric("Unique Male Entities (NER)", f"{stats['unique_masculine_entities']:,}")
