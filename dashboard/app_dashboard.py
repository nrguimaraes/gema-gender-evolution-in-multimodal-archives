"""
GEMA — Gender Evolution in Multimodal Archives
Interactive demonstrator dashboard built with Streamlit and Plotly.
Run: streamlit run dashboard/app_dashboard.py
"""
import sys
import os

# Allow running from project root or from dashboard/ folder
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
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
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Mega-events reference data
# ---------------------------------------------------------------------------

OLYMPICS = {2000: "Sydney", 2004: "Atenas", 2008: "Pequim",
             2012: "Londres", 2016: "Rio", 2021: "Tóquio", 2024: "Paris"}
WORLD_CUPS = {2002, 2006, 2010, 2014, 2018, 2022}
EURO_CUPS = {2000, 2004, 2008, 2012, 2016, 2020, 2024}

NEWSPAPERS = ["A Bola", "Record", "O Jogo"]
NEWSPAPER_COLORS = {"A Bola": "#e41a1c", "Record": "#377eb8", "O Jogo": "#4daf4a"}

# ---------------------------------------------------------------------------
# Sidebar — global filters
# ---------------------------------------------------------------------------

with st.sidebar:
    st.image("https://raw.githubusercontent.com/streamlit/streamlit/develop/docs/_static/favicon.png",
             width=40)
    st.title("GEMA")
    st.caption("Gender Evolution in Multimodal Archives · 1998–2024")
    st.divider()

    all_years = list(range(1998, 2025))
    year_range = st.slider(
        "Intervalo de Anos",
        min_value=1998, max_value=2024,
        value=(2016, 2024),
        help="Filtra todos os gráficos pelo intervalo de anos seleccionado."
    )

    selected_newspapers = st.multiselect(
        "Jornais",
        options=NEWSPAPERS,
        default=NEWSPAPERS,
        help="A Bola · Record · O Jogo"
    )
    if not selected_newspapers:
        selected_newspapers = NEWSPAPERS

    st.divider()

    # Check whether the false-positive classification field exists in the DB
    _fp_available = getattr(db, "fp_field_exists", lambda: False)()
    filter_fp = st.checkbox(
        "Filtrar Falsos Positivos Visuais",
        value=False,
        disabled=not _fp_available,
        help=(
            "Remove rostos classificados como modelos, publicidade ou "
            "companheiras das análises visuais — mantém apenas atletas. "
            "Requer que o campo 'person_type' esteja preenchido na base de dados."
            if _fp_available else
            "Indisponível: o campo 'person_type' ainda não está preenchido na base de dados. "
            "Será activado automaticamente quando o pipeline classificar os rostos por tipo."
        )
    )
    if not _fp_available:
        st.caption("🔒 Filtro FP indisponível — campo `person_type` ausente.")

    st.divider()
    show_olympics = st.checkbox("Mostrar Jogos Olímpicos", value=True)
    show_worldcups = st.checkbox("Mostrar Mundiais FIFA", value=True)
    show_euros = st.checkbox("Mostrar Europeus UEFA", value=False)

    st.divider()
    st.caption("🔬 Estágio CC3051 · GEMA · 2025")

# ---------------------------------------------------------------------------
# Data loading — all results are cached by db.py
# ---------------------------------------------------------------------------

with st.spinner("A carregar dados da base de dados…"):
    df_vis_raw     = db.fetch_visual_yearly(filter_fp=filter_fp)
    df_txt_raw     = db.fetch_text_yearly()
    df_corr        = db.fetch_visual_text_correlation()
    df_prom        = db.fetch_prominence_detail(filter_fp=filter_fp)
    df_ner         = db.fetch_top_entities(top_n=25)
    df_sports      = db.fetch_sports_breakdown()
    df_sports_yr   = db.fetch_sports_by_year()
    df_entity_dist = db.fetch_entity_distribution("feminine")
    df_sem         = db.fetch_semantic_keywords()

# Apply year and newspaper filters from the sidebar
def _apply_filters(df: pd.DataFrame, year_col="year", src_col="source") -> pd.DataFrame:
    if df.empty:
        return df
    mask = pd.Series([True] * len(df), index=df.index)
    if year_col in df.columns:
        mask &= df[year_col].between(*year_range)
    if src_col in df.columns:
        mask &= df[src_col].isin(selected_newspapers)
    return df[mask]

df_vis  = _apply_filters(df_vis_raw)
df_txt  = _apply_filters(df_txt_raw)
df_prom = _apply_filters(df_prom)

if not df_corr.empty and "year" in df_corr.columns:
    df_corr = df_corr[df_corr["year"].between(*year_range)]

# ---------------------------------------------------------------------------
# Header KPIs
# ---------------------------------------------------------------------------

st.title("GEMA — Representação de Género na Imprensa Desportiva Portuguesa")
st.caption(
    "Análise multimodal (visão computacional + NLP) da representação de género "
    "em *A Bola*, *Record* e *O Jogo* entre 1998 e 2024."
)

k1, k2, k3, k4 = st.columns(4)

def _safe_female_pct(df, gender_col="gender", count_col="count"):
    """Compute female percentage from a counts DataFrame."""
    if df.empty or gender_col not in df.columns:
        return 0.0
    tot = df[count_col].sum()
    fem = df.loc[df[gender_col] == "Woman", count_col].sum()
    return round(fem / tot * 100, 1) if tot else 0.0

vis_fem = _safe_female_pct(df_vis)
txt_fem = _safe_female_pct(df_txt, gender_col="text_gender")

k1.metric("Rostos Femininos (capas)", f"{vis_fem}%",
          help="Percentagem de rostos femininos detectados nas capas no período seleccionado.")
k2.metric("Artigos Femininos (texto)", f"{txt_fem}%",
          help="Percentagem de artigos cujo género dominante é feminino.")
total_faces = int(df_vis["count"].sum()) if not df_vis.empty else 0
k3.metric("Rostos Totais Detectados", f"{total_faces:,}",
          help="Total de detecções faciais pelo RetinaFace no período seleccionado.")
total_articles = int(df_txt["count"].sum()) if not df_txt.empty else 0
k4.metric("Artigos Analisados", f"{total_articles:,}",
          help="Total de artigos classificados pelo WikiNeural no período seleccionado.")

st.divider()

# ---------------------------------------------------------------------------
# Helper: overlay mega-event vertical lines on any Plotly figure
# ---------------------------------------------------------------------------

def add_event_lines(fig: go.Figure, y_max: float = 100) -> go.Figure:
    years_in_range = range(year_range[0], year_range[1] + 1)
    added_legends: set = set()

    for yr in years_in_range:
        if show_olympics and yr in OLYMPICS:
            label = f"🏅 {OLYMPICS[yr]} {yr}"
            show = "Olimpíadas" not in added_legends
            if show:
                added_legends.add("Olimpíadas")
            fig.add_vline(
                x=yr, line_dash="dot", line_color="#d62728", line_width=1.8,
                annotation_text=label, annotation_position="top right",
                annotation_font_size=10,
            )
        elif show_worldcups and yr in WORLD_CUPS:
            label = f"⚽ Mundial {yr}"
            fig.add_vline(
                x=yr, line_dash="dash", line_color="#ff7f0e", line_width=1.5,
                annotation_text=label, annotation_position="top right",
                annotation_font_size=10,
            )
        elif show_euros and yr in EURO_CUPS:
            label = f"🏆 Euro {yr}"
            fig.add_vline(
                x=yr, line_dash="longdash", line_color="#2ca02c", line_width=1.2,
                annotation_text=label, annotation_position="top right",
                annotation_font_size=10,
            )
    return fig


tab1, tab2, tab3 = st.tabs([
    "📈 Evolução Longitudinal",
    "👁️ Visual vs Textual",
    "🔍 Contexto & Diversidade",
])


# ===========================================================================
# TAB 1 — Longitudinal evolution and editorial coverage
# ===========================================================================

with tab1:
    st.subheader("Q1 · Evolução longitudinal da representação feminina (1998–2024)")
    st.caption(
        "Eixo visual: percentagem de rostos femininos nas capas (RetinaFace). "
        "Eixo textual: percentagem de artigos cujo género dominante é feminino (WikiNeural)."
    )

    def _yearly_female_pct_vis(df):
        """Compute yearly female face percentage from visual data."""
        if df.empty:
            return pd.DataFrame(columns=["year", "female_pct"])
        piv = df.groupby(["year", "gender"])["count"].sum().unstack(fill_value=0).reset_index()
        woman = piv.get("Woman", pd.Series(0, index=piv.index))
        man   = piv.get("Man",   pd.Series(0, index=piv.index))
        piv["female_pct"] = woman / (woman + man).replace(0, float("nan")) * 100
        return piv[["year", "female_pct"]].dropna()

    def _yearly_female_pct_txt(df):
        """Compute yearly female article percentage from text data."""
        if df.empty:
            return pd.DataFrame(columns=["year", "female_pct"])
        piv = df.groupby(["year", "text_gender"])["count"].sum().unstack(fill_value=0).reset_index()
        woman = piv.get("Woman", pd.Series(0, index=piv.index))
        man   = piv.get("Man",   pd.Series(0, index=piv.index))
        piv["female_pct"] = woman / (woman + man).replace(0, float("nan")) * 100
        return piv[["year", "female_pct"]].dropna()

    vis_evo = _yearly_female_pct_vis(df_vis)
    txt_evo = _yearly_female_pct_txt(df_txt)

    if vis_evo.empty and txt_evo.empty:
        st.info("Sem dados para o intervalo e jornais seleccionados.")
    else:
        fig_evo = go.Figure()

        if not vis_evo.empty:
            vis_evo["year"] = vis_evo["year"].astype(int)
            fig_evo.add_trace(go.Scatter(
                x=vis_evo["year"], y=vis_evo["female_pct"].round(2),
                mode="lines+markers", name="Visual · Capas",
                line=dict(color="#9467bd", width=3),
                marker=dict(size=8),
                connectgaps=True,
                hovertemplate="<b>%{x}</b><br>Visual: %{y:.1f}%<extra></extra>",
            ))
        else:
            st.caption("⚠️ Sem dados visuais para o intervalo seleccionado.")

        if not txt_evo.empty:
            txt_evo["year"] = txt_evo["year"].astype(int)
            fig_evo.add_trace(go.Scatter(
                x=txt_evo["year"], y=txt_evo["female_pct"].round(2),
                mode="lines+markers", name="Textual · Artigos",
                line=dict(color="#e377c2", width=3, dash="dot"),
                marker=dict(size=8),
                connectgaps=True,
                hovertemplate="<b>%{x}</b><br>Textual: %{y:.1f}%<extra></extra>",
            ))
        else:
            st.caption("⚠️ Sem dados textuais para o intervalo seleccionado.")

        fig_evo.update_layout(
            title="<b>Representação Feminina: Eixo Visual vs Textual (%)</b>",
            xaxis_title="Ano", yaxis_title="% Representação Feminina",
            xaxis=dict(tickmode="linear", dtick=1),
            hovermode="x unified",
            template="plotly_white", legend_title="Eixo",
            height=420,
        )
        add_event_lines(fig_evo)
        st.plotly_chart(fig_evo, use_container_width=True)

    st.divider()

    # Q5 — per-newspaper comparison
    st.subheader("Q5 · Cobertura por jornal: A Bola, Record e O Jogo")

    col_v, col_t = st.columns(2)

    with col_v:
        st.markdown("**Visual — Capas (%)** por jornal")
        if df_vis.empty or "Woman" not in df_vis["gender"].values:
            st.info("Sem dados visuais.")
        else:
            piv_vis_j = df_vis.groupby(["year", "source", "gender"])["count"].sum().unstack(fill_value=0).reset_index()
            woman = piv_vis_j.get("Woman", 0)
            man   = piv_vis_j.get("Man", 0)
            piv_vis_j["female_pct"] = woman / (woman + man).replace(0, float("nan")) * 100
            piv_vis_j = piv_vis_j.dropna(subset=["female_pct"])
            fig_vj = px.bar(
                piv_vis_j, x="year", y="female_pct", color="source",
                barmode="group", text_auto=".1f",
                color_discrete_map=NEWSPAPER_COLORS,
                labels={"female_pct": "% Rostos Femininos", "year": "Ano", "source": "Jornal"},
                height=360,
            )
            fig_vj.update_layout(template="plotly_white", xaxis=dict(tickmode="linear", dtick=1))
            add_event_lines(fig_vj, y_max=piv_vis_j["female_pct"].max() * 1.2)
            st.plotly_chart(fig_vj, use_container_width=True)

    with col_t:
        st.markdown("**Textual — Artigos (%)** por jornal")
        if df_txt.empty or "Woman" not in df_txt["text_gender"].values:
            st.info("Sem dados textuais.")
        else:
            piv_txt_j = df_txt.groupby(["year", "source", "text_gender"])["count"].sum().unstack(fill_value=0).reset_index()
            woman = piv_txt_j.get("Woman", 0)
            man   = piv_txt_j.get("Man", 0)
            piv_txt_j["female_pct"] = woman / (woman + man).replace(0, float("nan")) * 100
            piv_txt_j = piv_txt_j.dropna(subset=["female_pct"])
            fig_tj = px.bar(
                piv_txt_j, x="year", y="female_pct", color="source",
                barmode="group", text_auto=".1f",
                color_discrete_map=NEWSPAPER_COLORS,
                labels={"female_pct": "% Artigos Femininos", "year": "Ano", "source": "Jornal"},
                height=360,
            )
            fig_tj.update_layout(template="plotly_white", xaxis=dict(tickmode="linear", dtick=1))
            st.plotly_chart(fig_tj, use_container_width=True)

    st.divider()

    # Q4 — mega-event impact
    st.subheader("Q4 · O Efeito dos Megaeventos Desportivos na Representação Feminina")
    st.caption(
        "Comparação da cobertura feminina em anos olímpicos vs anos regulares. "
        "Hipótese: os JO impulsionam visibilidade feminina de forma transitória."
    )

    def _olympic_comparison(df_v, df_t):
        """Compare female coverage in Olympic years vs standard years."""
        olympic_yrs = [y for y in OLYMPICS if year_range[0] <= y <= year_range[1]]
        if not olympic_yrs:
            return None

        vis_e = _yearly_female_pct_vis(df_v)
        txt_e = _yearly_female_pct_txt(df_t)
        if vis_e.empty and txt_e.empty:
            return None

        rows = []
        for label, df_e, axis in [("Visual · Capas", vis_e, "visual"), ("Textual · Artigos", txt_e, "text")]:
            if df_e.empty:
                continue
            oly = df_e[df_e["year"].isin(olympic_yrs)]["female_pct"].mean()
            std = df_e[~df_e["year"].isin(olympic_yrs)]["female_pct"].mean()
            rows += [
                {"Eixo": label, "Tipo de Ano": "Ano Olímpico 🏅", "% Feminina": round(oly, 2)},
                {"Eixo": label, "Tipo de Ano": "Ano Regular", "% Feminina": round(std, 2)},
            ]
        return pd.DataFrame(rows) if rows else None

    oly_df = _olympic_comparison(df_vis, df_txt)
    if oly_df is None:
        st.info("Sem anos olímpicos no intervalo seleccionado para comparar.")
    else:
        fig_oly = px.bar(
            oly_df, x="Eixo", y="% Feminina", color="Tipo de Ano", barmode="group",
            text_auto=".2f",
            color_discrete_map={"Ano Olímpico 🏅": "#d62728", "Ano Regular": "#7f7f7f"},
            title="<b>O Efeito Olímpico: Cobertura Feminina em Anos de Jogos vs Anos Regulares</b>",
            height=380,
        )
        fig_oly.update_traces(textfont_size=13, textposition="outside", cliponaxis=False)
        fig_oly.update_layout(template="plotly_white", title_x=0.5)
        st.plotly_chart(fig_oly, use_container_width=True)

        with st.expander("ℹ️ Como interpretar"):
            st.markdown(
                "Barras vermelhas = média nos anos olímpicos do intervalo seleccionado. "
                "Se a barra vermelha for substancialmente maior, confirma-se o efeito de visibilidade transitória. "
                "Observar se a curva volta ao baseline no ano seguinte reforça a hipótese de 'spike olímpico'."
            )


# ===========================================================================
# TAB 2 — Visual axis vs textual axis
# ===========================================================================

with tab2:
    st.subheader("Q3 · Articulação entre Eixo Visual (Capas) e Eixo Textual (Artigos)")
    st.caption(
        "Cada ponto representa um ano. "
        "Correlação positiva forte indicaria que quando as mulheres aparecem mais nas capas, "
        "também são mais escritas nos artigos — e vice-versa."
    )

    if df_corr.empty:
        st.info("Dados insuficientes para calcular correlação (é necessário sobreposição de anos entre as duas coleções).")
    else:
        import numpy as np

        x_vals = df_corr["visual_female_pct"].values
        y_vals = df_corr["text_female_pct"].values

        # Manual OLS trendline — avoids the statsmodels optional dependency
        m, b = np.polyfit(x_vals, y_vals, 1)
        x_line = np.linspace(x_vals.min(), x_vals.max(), 100)

        fig_scatter = go.Figure()
        fig_scatter.add_trace(go.Scatter(
            x=x_vals, y=y_vals,
            mode="markers+text",
            text=df_corr["year"].astype(str),
            textposition="top center",
            marker=dict(size=10, color="#9467bd"),
            name="Anos",
            hovertemplate="<b>%{text}</b><br>Visual: %{x:.1f}%<br>Textual: %{y:.1f}%<extra></extra>",
        ))
        fig_scatter.add_trace(go.Scatter(
            x=x_line, y=m * x_line + b,
            mode="lines", line=dict(color="#ff7f0e", dash="dash", width=2),
            name=f"Tendência (y={m:.2f}x+{b:.2f})",
        ))
        fig_scatter.update_layout(
            title="<b>Correlação Visual–Textual: Rostos nas Capas vs Artigos sobre Mulheres</b>",
            xaxis_title="Rostos Femininos nas Capas (%)",
            yaxis_title="Artigos Femininos (%)",
            template="plotly_white", title_x=0.5, height=430,
        )
        st.plotly_chart(fig_scatter, use_container_width=True)

        corr_val = df_corr["visual_female_pct"].corr(df_corr["text_female_pct"])
        st.metric("Coeficiente de Correlação de Pearson (r)", f"{corr_val:.3f}",
                  help="r próximo de 1 = correlação positiva forte entre os dois eixos.")

    st.divider()

    # Q6 — visual prominence
    st.subheader("Q6 · Proeminência Visual — Área Ocupada na Capa (% de píxeis)")
    st.caption(
        "Área média das bounding boxes (RetinaFace) como percentagem da capa. "
        "Valores altos indicam que o rosto/corpo ocupa mais espaço editorial."
    )

    if df_prom.empty:
        st.info("Sem dados de proeminência para o período seleccionado.")
    else:
        prom_year = df_prom.groupby(["year", "gender"]).agg(
            avg_prominence=("avg_prominence", "mean"),
            total=("count", "sum"),
        ).reset_index()

        fig_prom = px.bar(
            prom_year, x="year", y="avg_prominence", color="gender", barmode="group",
            text_auto=".2f",
            color_discrete_map={"Man": "#1f77b4", "Woman": "#e377c2"},
            labels={"avg_prominence": "Área Média na Capa (%)", "year": "Ano", "gender": "Género"},
            title="<b>Proeminência Visual por Género: Área Média Ocupada nas Capas (%)</b>",
            height=380,
        )
        fig_prom.update_layout(template="plotly_white", title_x=0.5, xaxis=dict(tickmode="linear", dtick=1))
        add_event_lines(fig_prom)
        st.plotly_chart(fig_prom, use_container_width=True)

        # Woman-to-man prominence ratio per year
        ratio_df = prom_year.pivot(index="year", columns="gender", values="avg_prominence").reset_index()
        if "Woman" in ratio_df.columns and "Man" in ratio_df.columns:
            ratio_df["ratio_w_m"] = ratio_df["Woman"] / ratio_df["Man"].replace(0, float("nan"))
            fig_ratio = px.line(
                ratio_df, x="year", y="ratio_w_m", markers=True,
                labels={"ratio_w_m": "Rácio Área Mulher / Homem", "year": "Ano"},
                title="<b>Rácio de Proeminência: Área Feminina / Masculina (1.0 = paridade de tamanho)</b>",
                color_discrete_sequence=["#ff7f0e"],
                height=300,
            )
            fig_ratio.add_hline(y=1.0, line_dash="dash", line_color="grey",
                                annotation_text="Paridade", annotation_position="right")
            fig_ratio.update_layout(template="plotly_white", title_x=0.5, xaxis=dict(tickmode="linear", dtick=1))
            add_event_lines(fig_ratio)
            st.plotly_chart(fig_ratio, use_container_width=True)

        with st.expander("ℹ️ Notas metodológicas"):
            st.markdown(
                "- `cover_coverage_percentage` = área da bounding box / área total da capa × 100.  \n"
                "- Um rácio < 1 indica que rostos femininos ocupam em média menos espaço do que os masculinos.  \n"
                "- Picos acima de 1 podem reflectir capas especiais (ex: edições olímpicas) ou amostra reduzida."
            )


# ===========================================================================
# TAB 3 — Context, diversity and false positives
# ===========================================================================

with tab3:

    # False-positive filter status banner
    if not _fp_available:
        st.warning(
            "⏳ **Filtro de Falsos Positivos indisponível** — o campo `person_type` ainda não está "
            "preenchido na colecção `covers_analysis`. Os gráficos mostram todos os rostos detectados. "
            "Quando o pipeline classificar os rostos por tipo (atleta / modelo / publicidade / companheira), "
            "o filtro será activado automaticamente."
        )
    elif filter_fp:
        st.success(
            "✅ Filtro de Falsos Positivos **activo** — "
            "análises visuais excluem modelos / publicidade / companheiras (campo `person_type`)."
        )
    else:
        st.info(
            "ℹ️ Filtro de Falsos Positivos **inactivo**. "
            "Activa na barra lateral para restringir as análises visuais a atletas."
        )

    st.divider()

    # Q8 — protagonist diversity
    st.subheader("Q8 · Diversidade de Protagonistas: concentração ou pluralidade?")
    st.caption(
        "100 menções correspondem a 100 atletas diferentes ou à mesma atleta referida 100 vezes? "
        "O Índice HHI (Herfindahl-Hirschman) mede a concentração: 0 = diversidade total · 1 = monopólio."
    )

    if df_entity_dist.empty:
        st.info("Sem entidades nomeadas femininas na base de dados.")
    else:
        import numpy as np

        total_mentions = int(df_entity_dist["count"].sum())
        n_unique = len(df_entity_dist)
        shares = df_entity_dist["count"] / total_mentions
        hhi = round(float((shares ** 2).sum()), 4)

        # Normalised HHI: (HHI - 1/N) / (1 - 1/N) → 0 = perfectly diverse, 1 = monopoly
        hhi_norm = round((hhi - 1/n_unique) / (1 - 1/n_unique), 4) if n_unique > 1 else 1.0
        avg_mentions_per_entity = round(total_mentions / n_unique, 1) if n_unique else 0

        kc1, kc2, kc3, kc4 = st.columns(4)
        kc1.metric("Menções Totais", f"{total_mentions:,}",
                   help="Soma de todas as menções a entidades femininas nos artigos.")
        kc2.metric("Atletas / Protagonistas Únicas", f"{n_unique:,}",
                   help="Entidades femininas únicas identificadas pelo NER.")
        kc3.metric("Média de Menções por Atleta", f"{avg_mentions_per_entity}",
                   help="Se for muito > 1, a cobertura está concentrada.")
        kc4.metric("Índice HHI Normalizado", f"{hhi_norm:.3f}",
                   help="0 = diversidade máxima · 1 = monopólio absoluto (uma só atleta).")

        if hhi_norm > 0.5:
            st.error("🔴 Concentração **elevada** — a cobertura foca em poucas atletas-estrela.")
        elif hhi_norm > 0.15:
            st.warning("🟡 Concentração **moderada** — há alguma diversidade mas poucas atletas dominam.")
        else:
            st.success("🟢 Boa **diversidade** de protagonistas — menções distribuídas por muitas atletas.")

        col_left, col_right = st.columns(2)

        with col_left:
            top15 = df_entity_dist.head(15)
            fig_ner = px.bar(
                top15.sort_values("count"), x="count", y="entity", orientation="h",
                text_auto=True,
                labels={"count": "Nº de Menções", "entity": "Atleta / Protagonista"},
                title="<b>Top 15 Protagonistas Femininas (NER · WikiNeural)</b>",
                color="count", color_continuous_scale="PuRd",
                height=460,
            )
            fig_ner.update_layout(template="plotly_white", showlegend=False,
                                   coloraxis_showscale=False)
            st.plotly_chart(fig_ner, use_container_width=True)

        with col_right:
            # Rank-frequency (Zipf) plot — steep curve = star dependency, flat = diversity
            df_rank = df_entity_dist.reset_index(drop=True)
            df_rank["rank"] = df_rank.index + 1
            fig_zipf = go.Figure()
            fig_zipf.add_trace(go.Scatter(
                x=df_rank["rank"], y=df_rank["count"],
                mode="lines+markers",
                line=dict(color="#e377c2", width=2),
                marker=dict(size=5),
                hovertemplate="Rank %{x}: <b>%{customdata}</b><br>Menções: %{y}<extra></extra>",
                customdata=df_rank["entity"],
            ))
            fig_zipf.update_layout(
                title="<b>Distribuição Rank–Frequência (Lei de Zipf)</b>",
                xaxis_title="Rank da Atleta",
                yaxis_title="Nº de Menções",
                template="plotly_white", title_x=0.5, height=460,
            )
            fig_zipf.add_annotation(
                text=(
                    "Curva abrupta → concentração em estrelas<br>"
                    "Curva suave → diversidade real"
                ),
                xref="paper", yref="paper", x=0.95, y=0.95,
                showarrow=False, font=dict(size=10, color="grey"),
                align="right",
            )
            st.plotly_chart(fig_zipf, use_container_width=True)

        # Frequency histogram: how many athletes have X mentions
        mention_bins = pd.cut(
            df_entity_dist["count"],
            bins=[0, 1, 2, 5, 10, 20, 50, float("inf")],
            labels=["1", "2", "3–5", "6–10", "11–20", "21–50", "50+"],
        )
        bin_counts = mention_bins.value_counts().sort_index().rename("Nº de Atletas").reset_index()
        bin_counts.columns = ["Intervalo de Menções", "Nº de Atletas"]

        fig_hist = px.bar(
            bin_counts, x="Intervalo de Menções", y="Nº de Atletas",
            text_auto=True,
            title="<b>Quantas atletas têm X menções? (Distribuição de Frequência)</b>",
            color="Nº de Atletas", color_continuous_scale="Purp",
            height=320,
        )
        fig_hist.update_layout(template="plotly_white", title_x=0.5,
                                coloraxis_showscale=False)
        st.plotly_chart(fig_hist, use_container_width=True)

        with st.expander("ℹ️ Como interpretar o HHI e os gráficos"):
            st.markdown(
                "**HHI Normalizado:** calculado como Σ(sᵢ²), onde sᵢ = menções_i / total.  \n"
                "Normalizado para [0, 1] usando (HHI − 1/N) / (1 − 1/N).  \n\n"
                "**Distribuição rank–frequência:** se a curva cair muito depressa (cauda longa curta), "
                "poucas atletas concentram quase todas as menções — sinal de *estrela-dependência*.  \n\n"
                "**Histograma:** permite ler directamente quantas atletas 'existem uma só vez' "
                "no corpus vs quantas têm cobertura recorrente."
            )

    st.divider()

    # Q7 — sport modalities
    st.subheader("Q7 · Modalidades Desportivas que Impulsionam a Representação Feminina")
    st.caption(
        "Detecção baseada em keywords por modalidade nos artigos com género dominante feminino. "
        "Cruza entidades femininas com palavras-chave de desportos específicos para traçar o perfil das modalidades mais cobertas."
    )

    if df_sports.empty:
        st.info("Sem artigos femininos detectados para análise de modalidades.")
    else:
        col_sp1, col_sp2 = st.columns([2, 3])

        with col_sp1:
            fig_sports = px.bar(
                df_sports.head(12).sort_values("count"), x="count", y="sport",
                orientation="h", text_auto=True,
                labels={"count": "Nº de Artigos Femininos", "sport": "Modalidade"},
                title="<b>Modalidades com Mais Cobertura Feminina</b>",
                color="count", color_continuous_scale="Teal",
                height=420,
            )
            fig_sports.update_layout(template="plotly_white", showlegend=False,
                                      coloraxis_showscale=False)
            st.plotly_chart(fig_sports, use_container_width=True)

        with col_sp2:
            if not df_sports_yr.empty:
                # Keep only top 8 sports so the heatmap stays readable
                top_sports = df_sports.head(8)["sport"].tolist()
                df_heatmap = df_sports_yr[df_sports_yr["sport"].isin(top_sports)].copy()

                if not df_heatmap.empty:
                    pivot = df_heatmap.pivot_table(
                        index="sport", columns="year", values="count", aggfunc="sum", fill_value=0
                    )
                    pivot.columns = [int(c) for c in pivot.columns]
                    pivot = pivot[[c for c in pivot.columns if year_range[0] <= c <= year_range[1]]]

                    fig_heat = px.imshow(
                        pivot,
                        labels={"x": "Ano", "y": "Modalidade", "color": "Artigos"},
                        title="<b>Cobertura Feminina por Modalidade e Ano (Heatmap)</b>",
                        color_continuous_scale="Teal",
                        aspect="auto",
                        height=420,
                        text_auto=True,
                    )
                    fig_heat.update_layout(template="plotly_white", title_x=0.5)
                    add_event_lines(fig_heat)
                    st.plotly_chart(fig_heat, use_container_width=True)
                else:
                    st.info("Sem dados anuais por modalidade para o período seleccionado.")
            else:
                st.info("Sem dados anuais por modalidade disponíveis.")

        with st.expander("ℹ️ Metodologia de detecção de modalidades"):
            sport_kws = {k: ", ".join(v[:4]) + "…" for k, v in db.SPORT_KEYWORDS.items()}
            kw_df = pd.DataFrame(sport_kws.items(), columns=["Modalidade", "Exemplos de Keywords"])
            st.dataframe(kw_df, hide_index=True, use_container_width=True)
            st.caption(
                "Um artigo pode ser contado em mais do que uma modalidade se contiver keywords de ambas. "
                "A detecção é feita sobre o texto do título + corpo do artigo (lowercase)."
            )

    st.divider()

    # Q9 — semantic keyword analysis
    st.subheader("Q9 · Contexto Semântico da Cobertura Feminina")
    st.caption(
        "Keywords extraídas via YAKE! (unsupervised NLP) dos artigos classificados como femininos. "
        "Revelam se a cobertura se centra em performance desportiva ou em assuntos pessoais/maternidade."
    )

    @st.cache_data(ttl=600, show_spinner=False)
    def _run_yake(texts: tuple, top_n: int = 35) -> pd.DataFrame:
        """Run YAKE! keyword extraction on a tuple of texts."""
        if not texts:
            return pd.DataFrame(columns=["keyword", "score"])
        kw_extractor = yake.KeywordExtractor(lan="pt", n=2, dedupLim=0.8, top=top_n)
        combined = " ".join(t for t in texts if isinstance(t, str) and len(t) > 10)
        if len(combined) < 50:
            return pd.DataFrame(columns=["keyword", "score"])
        raw = kw_extractor.extract_keywords(combined)
        df_kw = pd.DataFrame(raw, columns=["keyword", "score"])
        # YAKE scores are inverted — lower score = more relevant
        df_kw["relevance"] = 1 - df_kw["score"]
        return df_kw.sort_values("relevance", ascending=False)

    if df_sem.empty:
        st.info("Sem artigos femininos para análise semântica no período seleccionado.")
    else:
        texts_tuple = tuple(df_sem["text"].tolist())
        with st.spinner("A extrair keywords com YAKE!…"):
            df_kw = _run_yake(texts_tuple)

        if df_kw.empty:
            st.info("Texto insuficiente para extracção de keywords.")
        else:
            fig_kw = px.bar(
                df_kw.head(25).sort_values("relevance"), x="relevance", y="keyword",
                orientation="h", text_auto=".3f",
                labels={"relevance": "Relevância (1 − score YAKE)", "keyword": "Keyword"},
                title="<b>Top 25 Keywords Associadas à Cobertura Feminina</b>",
                color="relevance", color_continuous_scale="Magenta",
                height=600,
            )
            fig_kw.update_layout(template="plotly_white", showlegend=False,
                                  coloraxis_showscale=False)
            st.plotly_chart(fig_kw, use_container_width=True)

            with st.expander("🔎 Tabela completa de keywords"):
                st.dataframe(df_kw, use_container_width=True, hide_index=True)

            with st.expander("ℹ️ Interpretação"):
                st.markdown(
                    "- **Score YAKE baixo** = keyword mais relevante no corpus.  \n"
                    "- Keywords como *performance*, *medalha*, *vitória*, *campeonato* apontam para **cobertura desportiva**.  \n"
                    "- Keywords como *família*, *maternidade*, *relação*, *namorado* apontam para **cobertura da esfera pessoal**.  \n"
                    "- Esta dicotomia é central na Q9 da investigação GEMA."
                )

    st.divider()

    # Pipeline health summary
    st.subheader("📊 Estado do Pipeline (amostra actual)")
    with st.spinner("A calcular estatísticas do pipeline…"):
        stats = db.fetch_pipeline_stats()

    s1, s2, s3, s4 = st.columns(4)
    s1.metric("Taxa de Classificação (Texto)", f"{stats['classification_rate_pct']}%",
              help="Artigos classificados / total artigos raw.")
    s2.metric("Faces c/ Alta Confiança (≥0.90)", f"{stats['high_conf_rate_pct']}%",
              help="Percentagem de detecções com gender_confidence ≥ 0.90.")
    s3.metric("Entidades Femininas Únicas (NER)", f"{stats['unique_feminine_entities']:,}")
    s4.metric("Entidades Masculinas Únicas (NER)", f"{stats['unique_masculine_entities']:,}")
