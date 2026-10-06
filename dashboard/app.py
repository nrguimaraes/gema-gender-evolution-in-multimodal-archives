"""
GEMA — Gender Evolution in Multimodal Archives
Interactive dashboard — HuggingFace Space version (static data, no MongoDB).
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import yake
import io
from wordcloud import WordCloud
import matplotlib.pyplot as plt

import db_static as db

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="GEMA · Explorer",
    page_icon="🔭",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    .block-container { padding-top: 1.5rem; }
    h1 { font-size: 1.6rem !important; }
    .stTabs [data-baseweb="tab"] { font-size: 0.95rem; }
    .insight-box {
        background: #f0f2f6;
        border-left: 4px solid #9467bd;
        padding: 0.6rem 1rem;
        border-radius: 4px;
        font-size: 0.85rem;
        margin: 0.4rem 0;
    }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Reference data
# ---------------------------------------------------------------------------

OLYMPICS       = {2000: "Sydney", 2004: "Athens", 2008: "Beijing",
                  2012: "London", 2016: "Rio", 2021: "Tokyo", 2024: "Paris"}
MENS_WC        = {2002, 2006, 2010, 2014, 2018, 2022}
WOMENS_WC      = {1999, 2003, 2007, 2011, 2015, 2019, 2023}
EURO_CUPS      = {2000, 2004, 2008, 2012, 2016, 2020, 2024}

SOURCE_COLORS = {
    "A Bola":             "#e41a1c",
    "Record":             "#377eb8",
    "O Jogo":             "#4daf4a",
    "SAPO":               "#ff7f00",
    "Notícias ao Minuto": "#984ea3",
    "ZAP":                "#a65628",
    "Euronews":           "#f781bf",
}
ALL_SOURCES   = list(SOURCE_COLORS.keys())
PRINT_SOURCES = ["A Bola", "Record", "O Jogo"]

EVENT_COLORS = {
    "Olympic year":      "#ff7f0e",
    "Men's World Cup":   "#1f77b4",
    "Women's World Cup": "#e377c2",
    "UEFA Euro":         "#2ca02c",
    "Standard year":     "#7f7f7f",
}

def event_label(year: int) -> str:
    if year in OLYMPICS:
        return "Olympic year"
    if year in MENS_WC:
        return "Men's World Cup"
    if year in WOMENS_WC:
        return "Women's World Cup"
    if year in EURO_CUPS:
        return "UEFA Euro"
    return "Standard year"

# ---------------------------------------------------------------------------
# Sidebar — global controls
# ---------------------------------------------------------------------------

with st.sidebar:
    st.title("🔭 GEMA Explorer")
    st.caption("28 years of women's representation in Portuguese sports media.")
    st.divider()

    year_range = st.slider(
        "Year range", 1998, 2026, (1998, 2026),
        help="Filter all charts to a specific time window.",
    )

    selected_sources = st.multiselect(
        "Outlets",
        ALL_SOURCES,
        default=ALL_SOURCES,
        help="Select which newspapers to include. Deselecting all restores the full set.",
    )
    if not selected_sources:
        selected_sources = ALL_SOURCES

    st.divider()

    st.markdown("**Event markers**")
    show_olympics  = st.checkbox("Olympic Games",     value=True,
        help="Mark Olympic Games years on trend charts.")
    show_mens_wc   = st.checkbox("Men's World Cup",   value=False,
        help="Mark Men's Football World Cup years on trend charts.")
    show_womens_wc = st.checkbox("Women's World Cup", value=True,
        help="Mark Women's Football World Cup years on trend charts.")
    show_euros     = st.checkbox("UEFA Euro",          value=False,
        help="Mark UEFA European Championship years on trend charts.")

    st.divider()
    body_only = st.checkbox(
        "Full-text articles only",
        value=True,
        help="Exclude articles where only the headline was available.",
    )
    st.divider()
    st.caption("GEMA · 2025")

# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def _safe(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except Exception as e:
        st.warning(f"Could not load `{fn.__name__}`: {e}")
        return pd.DataFrame()

with st.spinner("Loading data…"):
    df_vis_raw    = _safe(db.fetch_visual_yearly, filter_prominent=False)
    df_txt_raw    = _safe(db.fetch_text_yearly, filter_body=body_only)
    df_ent_dist   = _safe(db.fetch_entity_distribution, "feminine")
    df_ent_dist_m = _safe(db.fetch_entity_distribution, "masculine")
    df_sports     = _safe(db.fetch_sports_breakdown)
    df_sports_yr  = _safe(db.fetch_sports_by_year)


def _filt(df, src_col="source"):
    if df.empty:
        return df
    out = df[df["year"].between(*year_range)] if "year" in df.columns else df
    out = out[out[src_col].isin(selected_sources)] if src_col in df.columns else out
    return out

df_vis = _filt(df_vis_raw)
df_txt = _filt(df_txt_raw)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def female_pct(df, gcol, count_col="count"):
    if df.empty or gcol not in df.columns:
        return 0.0
    tot = df[count_col].sum()
    fem = df.loc[df[gcol] == "Woman", count_col].sum()
    return round(fem / tot * 100, 1) if tot else 0.0

def add_event_lines(fig):
    for yr in range(year_range[0], year_range[1] + 1):
        if show_olympics and yr in OLYMPICS:
            fig.add_vline(x=yr, line_dash="dot", line_color="#d62728", line_width=1.5,
                          annotation_text=f"🏅 {yr}", annotation_font_size=9)
        elif show_mens_wc and yr in MENS_WC:
            fig.add_vline(x=yr, line_dash="dash", line_color="#ff7f0e", line_width=1.2,
                          annotation_text=f"⚽ {yr}", annotation_font_size=9)
        elif show_womens_wc and yr in WOMENS_WC:
            fig.add_vline(x=yr, line_dash="dash", line_color="#e377c2", line_width=1.2,
                          annotation_text=f"⚽W {yr}", annotation_font_size=9)
        elif show_euros and yr in EURO_CUPS:
            fig.add_vline(x=yr, line_dash="longdash", line_color="#2ca02c", line_width=1.1,
                          annotation_text=f"🏆 {yr}", annotation_font_size=9)
    return fig

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------

st.title("🔭 GEMA — Women's Representation in Portuguese Sports Media")
st.caption("Explore 28 years of data freely.")

vis_fem = female_pct(df_vis, "gender")
txt_fem = female_pct(df_txt, "text_gender")
total_articles = int(df_txt["count"].sum()) if not df_txt.empty else 0
total_faces    = int(df_vis["count"].sum()) if not df_vis.empty else 0

k1, k2, k3, k4 = st.columns(4)
k1.metric("Female on covers",  f"{vis_fem}%",  help="% of detected faces classified as female")
k2.metric("Female in articles", f"{txt_fem}%", help="% of articles with a female protagonist")
k3.metric("Faces analysed",    f"{total_faces:,}")
k4.metric("Articles analysed", f"{total_articles:,}")

st.divider()

# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------

tab_explore, tab_events, tab_sources, tab_athletes = st.tabs([
    "📊 Explore",
    "🏅 Events",
    "📰 By Source",
    "🏃 Athlete Explorer",
])

# ===========================================================================
# TAB 1 — Free explorer
# ===========================================================================

with tab_explore:
    st.subheader("Build your own view")

    ctrl1, ctrl2, ctrl3 = st.columns(3)
    with ctrl1:
        data_axis = st.radio(
            "Data",
            ["Text (articles)", "Visual (covers)", "Both"],
            horizontal=True,
        )
    with ctrl2:
        metric = st.radio(
            "Metric",
            ["Female % over time", "Male vs Female (stacked)", "Female article counts"],
            horizontal=True,
        )
    with ctrl3:
        split_by = st.radio(
            "Split by",
            ["None", "Newspaper"],
            horizontal=True,
        )

    axes_to_show = []
    if data_axis in ("Text (articles)", "Both"):
        axes_to_show.append(("text", df_txt, "text_gender", "Articles"))
    if data_axis in ("Visual (covers)", "Both"):
        axes_to_show.append(("visual", df_vis, "gender", "Covers"))

    chart_cols = st.columns(len(axes_to_show))

    for col, (ax_key, df_ax, gcol, label) in zip(chart_cols, axes_to_show):
        with col:
            st.markdown(f"**{'📰' if ax_key == 'text' else '🗞️'} {label}**")

            if df_ax.empty:
                st.info("No data.")
                continue

            df_w = df_ax[df_ax[gcol] == "Woman"]
            df_m = df_ax[df_ax[gcol] == "Man"]

            if metric == "Female % over time":
                piv = df_ax.groupby(["year", gcol])["count"].sum().unstack(fill_value=0).reset_index()
                piv["female_pct"] = (
                    piv.get("Woman", 0) /
                    (piv.get("Woman", 0) + piv.get("Man", 0)).replace(0, float("nan")) * 100
                ).round(2)

                if split_by == "Newspaper":
                    src_piv = df_ax.groupby(["year", "source", gcol])["count"].sum().unstack(fill_value=0).reset_index()
                    src_piv["female_pct"] = (
                        src_piv.get("Woman", 0) /
                        (src_piv.get("Woman", 0) + src_piv.get("Man", 0)).replace(0, float("nan")) * 100
                    ).round(2)
                    fig = px.line(
                        src_piv, x="year", y="female_pct", color="source",
                        color_discrete_map=SOURCE_COLORS, markers=True,
                        labels={"year": "Year", "female_pct": "Female %", "source": "Source"},
                    )
                else:
                    fig = px.line(piv, x="year", y="female_pct", markers=True,
                                  labels={"year": "Year", "female_pct": "Female %"})
                    fig.update_traces(line_color="#e377c2", marker_color="#e377c2", line_width=3)
                    avg = piv["female_pct"].mean()
                    fig.add_hline(y=avg, line_dash="dash", line_color="#9467bd",
                                  annotation_text=f"avg {avg:.1f}%")
                    fig.add_hline(y=50, line_dash="dot", line_color="lightgray")

                add_event_lines(fig)
                fig.update_layout(
                    height=400, template="plotly_white",
                    xaxis=dict(tickmode="linear", dtick=2),
                    yaxis_title="Female %",
                )

            elif metric == "Male vs Female (stacked)":
                if split_by == "Newspaper":
                    agg = df_ax.groupby(["year", "source", gcol])["count"].sum().reset_index()
                    fig = px.bar(
                        agg, x="year", y="count", color=gcol, facet_col="source",
                        barmode="stack",
                        color_discrete_map={"Woman": "#e377c2", "Man": "#1f77b4"},
                        labels={"year": "Year", "count": label, gcol: "Gender"},
                    )
                else:
                    agg = df_ax.groupby(["year", gcol])["count"].sum().reset_index()
                    fig = px.bar(
                        agg, x="year", y="count", color=gcol, barmode="stack",
                        color_discrete_map={"Woman": "#e377c2", "Man": "#1f77b4"},
                        labels={"year": "Year", "count": label, gcol: "Gender"},
                    )
                add_event_lines(fig)
                fig.update_layout(height=400, template="plotly_white",
                                  xaxis=dict(tickmode="linear", dtick=2))

            else:  # Female article counts
                agg_w = df_w.groupby("year")["count"].sum().reset_index().rename(columns={"count": "female"})
                if split_by == "Newspaper":
                    agg_ws = df_w.groupby(["year", "source"])["count"].sum().reset_index()
                    fig = px.bar(
                        agg_ws, x="year", y="count", color="source",
                        color_discrete_map=SOURCE_COLORS,
                        labels={"year": "Year", "count": f"Female {label.lower()}", "source": "Source"},
                    )
                else:
                    fig = px.bar(
                        agg_w, x="year", y="female",
                        labels={"year": "Year", "female": f"Female {label.lower()}"},
                        color_discrete_sequence=["#e377c2"],
                    )
                add_event_lines(fig)
                fig.update_layout(height=400, template="plotly_white",
                                  xaxis=dict(tickmode="linear", dtick=2))

            st.plotly_chart(fig, use_container_width=True)

            with st.expander("Raw data"):
                if metric == "Female % over time":
                    st.dataframe(piv[["year", "female_pct"]].rename(columns={"female_pct": "Female %"}),
                                 use_container_width=True, hide_index=True)
                else:
                    grp = ["year", "source"] if split_by == "Newspaper" else ["year"]
                    st.dataframe(df_ax.groupby(grp + [gcol])["count"].sum().reset_index(),
                                 use_container_width=True, hide_index=True)


# ===========================================================================
# TAB 2 — Events
# ===========================================================================

with tab_events:
    st.subheader("How do major sporting events affect female coverage?")
    st.caption("Compare mean female representation across event years and standard years.")

    q4_events = st.multiselect(
        "Events to compare",
        ["Olympic Games", "Men's World Cup", "Women's World Cup", "UEFA Euro"],
        default=["Olympic Games", "Women's World Cup"],
    )

    EVENT_YEAR_MAP = {
        "Olympic Games":      set(OLYMPICS.keys()),
        "Men's World Cup":    MENS_WC,
        "Women's World Cup":  WOMENS_WC,
        "UEFA Euro":          EURO_CUPS,
    }

    if q4_events:
        def tag_event(year):
            for ev in q4_events:
                if year in EVENT_YEAR_MAP[ev]:
                    return ev
            return "Standard Year"

        rows = []
        for axis_label, df_ax, gcol in [
            ("Text",   df_txt, "text_gender"),
            ("Visual", df_vis, "gender"),
        ]:
            if df_ax.empty:
                continue
            piv = df_ax.groupby(["year", gcol])["count"].sum().unstack(fill_value=0).reset_index()
            if "Woman" not in piv.columns:
                continue
            piv["female_pct"] = (
                piv["Woman"] / (piv["Woman"] + piv.get("Man", 0)).replace(0, float("nan")) * 100
            )
            piv["event_type"] = piv["year"].apply(tag_event)
            for ev in q4_events + ["Standard Year"]:
                sub = piv[piv["event_type"] == ev]["female_pct"]
                if len(sub):
                    rows.append({"Axis": axis_label, "Event": ev,
                                 "Female Coverage (%)": round(sub.mean(), 2),
                                 "Years": ", ".join(str(y) for y in piv[piv["event_type"] == ev]["year"].tolist())})

        if rows:
            df_q4 = pd.DataFrame(rows)
            color_map = {
                "Olympic Games":    "#d62728",
                "Men's World Cup":  "#ff7f0e",
                "Women's World Cup":"#e377c2",
                "UEFA Euro":        "#2ca02c",
                "Standard Year":    "#7f7f7f",
            }
            fig_ev = px.bar(
                df_q4, x="Axis", y="Female Coverage (%)", color="Event",
                barmode="group", text_auto=".2f",
                color_discrete_map=color_map,
                hover_data=["Years"],
                height=420,
            )
            fig_ev.update_traces(textfont_size=13, textposition="outside", cliponaxis=False)
            fig_ev.update_layout(template="plotly_white")
            st.plotly_chart(fig_ev, use_container_width=True)

            st.dataframe(df_q4, use_container_width=True, hide_index=True)
    else:
        st.info("Select at least one event type above.")


# ===========================================================================
# TAB 3 — By source
# ===========================================================================

with tab_sources:
    st.subheader("Compare newspapers and outlets")

    src_view = st.radio("View", ["Heatmap", "Bar chart", "Line chart"], horizontal=True)
    src_axis = st.radio("Axis", ["Text", "Visual", "Both"], horizontal=True)
    print_only = st.checkbox("Print dailies only (A Bola, Record, O Jogo)", value=False)

    axes_src = []
    if src_axis in ("Text", "Both"):
        axes_src.append(("text", df_txt, "text_gender", "Articles"))
    if src_axis in ("Visual", "Both"):
        vis_src = df_vis[df_vis["source"].isin(PRINT_SOURCES)] if print_only else df_vis
        axes_src.append(("visual", vis_src, "gender", "Covers"))

    src_cols = st.columns(len(axes_src))

    for col, (ax_key, df_ax, gcol, label) in zip(src_cols, axes_src):
        df_plot = df_ax[df_ax["source"].isin(PRINT_SOURCES)] if print_only else df_ax
        with col:
            st.markdown(f"**{label}**")
            if df_plot.empty:
                st.info("No data.")
                continue

            piv = df_plot.groupby(["year", "source", gcol])["count"].sum().unstack(fill_value=0).reset_index()
            if "Woman" not in piv.columns:
                st.info("No female data.")
                continue
            piv["female_pct"] = (
                piv["Woman"] / (piv["Woman"] + piv.get("Man", 0)).replace(0, float("nan")) * 100
            ).round(1)
            piv = piv.dropna(subset=["female_pct"])

            if src_view == "Heatmap":
                pivot_h = piv.pivot_table(index="source", columns="year",
                                          values="female_pct", aggfunc="mean").round(1)
                fig_s = go.Figure(go.Heatmap(
                    z=pivot_h.values,
                    x=[str(c) for c in pivot_h.columns],
                    y=pivot_h.index.tolist(),
                    colorscale="RdPu",
                    text=[[f"{v:.1f}%" if not pd.isna(v) else "" for v in row] for row in pivot_h.values],
                    texttemplate="%{text}",
                    hovertemplate="<b>%{y}</b> · %{x}<br>Female: %{z:.1f}%<extra></extra>",
                    colorbar=dict(title="Female %"),
                ))
                fig_s.update_layout(
                    template="plotly_white",
                    height=max(250, len(pivot_h) * 50 + 80),
                    xaxis=dict(tickangle=45),
                )
            elif src_view == "Bar chart":
                fig_s = px.bar(
                    piv, x="year", y="female_pct", color="source",
                    barmode="group", text_auto=".1f",
                    color_discrete_map=SOURCE_COLORS,
                    labels={"female_pct": "Female %", "year": "Year", "source": "Source"},
                    height=400,
                )
                fig_s.update_layout(template="plotly_white",
                                    xaxis=dict(tickmode="linear", dtick=2))
            else:  # Line chart
                fig_s = px.line(
                    piv, x="year", y="female_pct", color="source",
                    color_discrete_map=SOURCE_COLORS, markers=True,
                    labels={"female_pct": "Female %", "year": "Year", "source": "Source"},
                    height=400,
                )
                fig_s.update_layout(template="plotly_white",
                                    xaxis=dict(tickmode="linear", dtick=2))
                add_event_lines(fig_s)

            st.plotly_chart(fig_s, use_container_width=True)


# ===========================================================================
# TAB 4 — Athlete Explorer
# ===========================================================================

with tab_athletes:
    st.subheader("🏃 Athlete Explorer")
    st.info("ℹ️ The sidebar filters (year range, outlets, event markers) do not apply to this tab.", icon=None)

    if df_ent_dist.empty:
        st.info("No athlete data available.")
        st.stop()

    # ── 1. Top female protagonists (full width) ──────────────────────────────
    st.markdown("**Top female protagonists (all sources)**")
    top_n = st.slider("Show top N", 5, 50, 20, key="top_n_ath")
    top_df = df_ent_dist.head(top_n)
    fig_top = px.bar(
        top_df.sort_values("count"), x="count", y="entity",
        orientation="h", text_auto=True,
        labels={"count": "Articles", "entity": ""},
        color="count", color_continuous_scale="PuRd",
        height=max(350, top_n * 20),
    )
    fig_top.update_layout(template="plotly_white", showlegend=False,
                          coloraxis_showscale=False)
    st.plotly_chart(fig_top, use_container_width=True)

    # ── 2. Search bar (full width) ────────────────────────────────────────────
    st.divider()
    athlete_options = df_ent_dist["entity"].tolist()
    selected = st.selectbox("🔍 Search athlete", athlete_options,
                             placeholder="Type a name to search…")

    if not selected:
        st.stop()

    with st.spinner(f"Loading data for {selected}…"):
        df_ath = _safe(db.fetch_athlete_articles, selected, "feminine")

    if df_ath.empty:
        st.info("No articles found.")
        st.stop()

    yr_counts = df_ath["year"].value_counts()
    top_year  = int(yr_counts.idxmax()) if not yr_counts.empty else "N/A"
    top_src   = df_ath["source"].value_counts().idxmax() if not df_ath["source"].empty else "N/A"

    # ── 3. Photo | Wikidata info stacked | Articles per year ─────────────────
    st.divider()
    col_photo, col_info, col_chart = st.columns([1, 1, 2])

    wd = {}
    try:
        sys.path.insert(0, os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "src", "utils")
        ))
        from wikidata_api import consultar_wikidata_info_completa
        with st.spinner("Fetching Wikidata…"):
            wd = consultar_wikidata_info_completa(selected)
    except Exception:
        pass

    with col_photo:
        img_url = wd.get("image_url")
        if img_url:
            try:
                import requests as _req
                r = _req.get(img_url, timeout=8, allow_redirects=True)
                if r.status_code == 200 and "image" in r.headers.get("Content-Type", ""):
                    st.image(r.content, caption=selected, use_container_width=True)
                else:
                    st.image(img_url, caption=selected, use_container_width=True)
            except Exception:
                st.image(img_url, caption=selected, use_container_width=True)
        else:
            st.caption("No photo available.")

    with col_info:
        st.markdown(f"#### {selected}")
        if wd:
            st.metric("Sport",       wd.get("sport")       or "Unknown")
            st.metric("Nationality", wd.get("nationality") or "Unknown")
            st.metric("Birth Year",  str(wd.get("birth_year") or "Unknown"))
            wd_url = wd.get("wikidata_url")
            if wd_url:
                st.markdown(f"[🔗 Wikidata page]({wd_url})")
            else:
                search_url = f"https://www.wikidata.org/w/index.php?search={selected.replace(' ', '+')}"
                st.markdown(f"[🔍 Search on Wikidata]({search_url})")
        else:
            st.caption("Wikidata information not available.")

    with col_chart:
        m1, m2, m3 = st.columns(3)
        m1.metric("Total Articles",   len(df_ath))
        m2.metric("Peak Year",        top_year)
        m3.metric("Most Coverage In", top_src)
        df_yr = yr_counts.sort_index().reset_index()
        df_yr.columns = ["Year", "Articles"]
        fig_ath = px.bar(
            df_yr, x="Year", y="Articles",
            title=f"<b>{selected} — Articles per Year</b>",
            color_discrete_sequence=["#e377c2"],
            height=420,
        )
        fig_ath.update_layout(template="plotly_white",
                              xaxis=dict(tickmode="linear", dtick=1))
        st.plotly_chart(fig_ath, use_container_width=True)

    # ── 4. Coverage by outlet | Keywords word cloud ───────────────────────────
    st.divider()
    col_pie, col_kw = st.columns([1, 1])

    with col_pie:
        st.markdown("**Coverage by outlet**")
        src_counts = df_ath["source"].value_counts().reset_index()
        src_counts.columns = ["Source", "Articles"]
        fig_src = px.pie(
            src_counts, names="Source", values="Articles",
            color="Source", color_discrete_map=SOURCE_COLORS,
            height=320,
        )
        fig_src.update_traces(textposition="inside", textinfo="percent+label")
        fig_src.update_layout(showlegend=False, template="plotly_white")
        st.plotly_chart(fig_src, use_container_width=True)

    with col_kw:
        st.markdown("**Key terms & entities**")
        all_text = " ".join(df_ath["content"].dropna().tolist())
        name_tokens = [t.lower() for t in selected.split() if len(t) > 2]

        kws = []
        kw_scores = {}
        if len(all_text) > 100:
            kw_ext = yake.KeywordExtractor(lan="pt", n=2, dedupLim=0.8, top=20)
            raw_kws = kw_ext.extract_keywords(all_text)
            filtered = [(kw, score) for kw, score in raw_kws
                        if not any(tok in kw.lower() for tok in name_tokens)]
            kws = [kw for kw, _ in filtered[:15]]
            max_score = max((s for _, s in filtered[:15]), default=1)
            kw_scores = {kw: max_score / score for kw, score in filtered[:15]}

        if kws:
            wc_img = WordCloud(
                width=600, height=220,
                background_color=None, mode="RGBA",
                colormap="RdPu",
                prefer_horizontal=0.85,
                max_words=15,
            ).generate_from_frequencies(kw_scores)

            buf = io.BytesIO()
            fig_wc, ax = plt.subplots(figsize=(6, 2.2))
            ax.imshow(wc_img, interpolation="bilinear")
            ax.axis("off")
            fig_wc.patch.set_alpha(0)
            plt.tight_layout(pad=0)
            fig_wc.savefig(buf, format="png", bbox_inches="tight",
                           transparent=True, dpi=150)
            plt.close(fig_wc)
            buf.seek(0)
            st.image(buf, use_container_width=True)

            sel_kw = st.selectbox("Explore keyword by outlet:", kws, key="kw_sel")
            if sel_kw:
                mask = df_ath["content"].fillna("").str.contains(
                    sel_kw, case=False, regex=False)
                kw_src = df_ath[mask]["source"].value_counts().reset_index()
                kw_src.columns = ["Outlet", "Articles"]
                if not kw_src.empty:
                    fig_kw = px.bar(
                        kw_src, x="Outlet", y="Articles",
                        color="Outlet", color_discrete_map=SOURCE_COLORS,
                        text_auto=True, height=200,
                    )
                    fig_kw.update_layout(template="plotly_white",
                                         showlegend=False,
                                         xaxis_title="", yaxis_title="Articles")
                    st.plotly_chart(fig_kw, use_container_width=True)
        else:
            st.caption("Not enough text to extract keywords.")

    # ── 5. Coverage Concentration (Zipf) ─────────────────────────────────────
    st.divider()
    st.markdown("#### 📉 Coverage Concentration (Zipf)")
    st.caption("How spread out is coverage? A steep drop means a few athletes dominate; a gradual slope means broader coverage.")

    zipf_mode = st.radio("Y-axis", ["Normalised (0–100%)", "Log scale"], horizontal=True)
    show_male = st.checkbox("Show male protagonists for comparison", value=True)

    fig_zipf = go.Figure()

    def _zipf_trace(fig, df_d, name, color):
        df_r = df_d.reset_index(drop=True).copy()
        df_r["rank"] = df_r.index + 1
        if "Norm" in zipf_mode:
            df_r["y"] = (df_r["count"] / df_r["count"].max() * 100).round(2)
        else:
            df_r["y"] = df_r["count"]
        fig.add_trace(go.Scatter(
            x=df_r["rank"], y=df_r["y"], mode="lines", name=name,
            line=dict(color=color, width=2),
            customdata=df_r["entity"],
            hovertemplate="Rank %{x}: <b>%{customdata}</b><br>%{y:.1f}<extra></extra>",
        ))

    if not df_ent_dist.empty:
        _zipf_trace(fig_zipf, df_ent_dist, "Female", "#e377c2")
    if show_male and not df_ent_dist_m.empty:
        _zipf_trace(fig_zipf, df_ent_dist_m, "Male", "#1f77b4")

    fig_zipf.update_layout(
        xaxis_title="Protagonist rank",
        yaxis_title="Share of top-1 (%)" if "Norm" in zipf_mode else "Mentions",
        yaxis_type="log" if "Log" in zipf_mode else "linear",
        template="plotly_white", height=380, legend_title="Gender",
    )
    st.plotly_chart(fig_zipf, use_container_width=True)
