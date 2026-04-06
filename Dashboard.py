import streamlit as st
import pandas as pd
import plotly.express as px
import os
from scipy.stats import pearsonr

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(layout="wide", page_title="Dashboard Educativo | UPAEP", page_icon="🔴")

# --- CSS: ESTÉTICA UNIFICADA Y ALTO CONTRASTE ---
st.markdown("""
    <style>
    .stApp { background-color: #F5F5F5; }
    [data-testid="stSidebar"] { background-color: #E0E0E0; border-right: 4px solid #CF091C; }
    
    /* FORZAR TEXTO NEGRO EN LA INTERFAZ GENERAL */
    h1, h2, h3, h4, p, span, label, .stMarkdown { color: #000000 !important; font-family: 'Segoe UI', sans-serif; }
    
    /* TARJETAS KPI UNIFICADAS (TODAS DELIMITADAS) */
    .kpi-card {
        background-color: #FFFFFF;
        border: 1px solid #CCCCCC;
        padding: 15px;
        border-radius: 8px;
        box-shadow: 2px 2px 5px rgba(0,0,0,0.05);
        text-align: center;
        margin-bottom: 10px;
        height: 120px;
        display: flex;
        flex-direction: column;
        justify-content: center;
    }
    .kpi-label { font-size: 0.85rem; font-weight: bold; color: #333333 !important; text-transform: uppercase; margin-bottom: 5px; }
    .kpi-value { font-size: 1.8rem; font-weight: 800; margin: 0; }

    /* BOTÓN DE RIESGO ESTILIZADO */
    div.stButton > button {
        width: 100%;
        background-color: #CF091C !important;
        color: white !important;
        border-radius: 5px;
        border: none;
        font-weight: bold;
        transition: 0.3s;
    }
    div.stButton > button:hover {
        background-color: #000000 !important;
        transform: scale(1.02);
    }

    /* TÍTULOS */
    .main-title { color: #CF091C !important; font-weight: 900; font-size: 2.8rem; margin-bottom: 0; }
    .author-tag { color: #000000 !important; font-size: 1.1rem; margin-bottom: 20px; font-weight: 400; }
    </style>
    """, unsafe_allow_html=True)

# --- CARGA DE DATOS ---
@st.cache_data
def load_data():
    file = "SantiagoDB.xlsx"
    if not os.path.exists(file): return None
    df = pd.read_excel(file, sheet_name="BD")
    
    cols_num = ['CF.', 'P1', 'P2', 'P3', '%Asis', 'F1', 'F2', 'F3']
    for c in cols_num:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c].astype(str).str.replace(',', '.'), errors='coerce').fillna(0)
    
    df['Total_Faltas'] = df[['F1', 'F2', 'F3']].sum(axis=1)
    df['Alumno_Full'] = df['Nombre'].astype(str) + " " + df['Apellido Paterno'].astype(str)
    
    # Lógica de Riesgo
    df['EsRiesgo'] = df.apply(lambda r: "SÍ" if r['CF.'] < 6 or r['%Asis'] < 80 else "NO", axis=1)
    return df

df_raw = load_data()

if df_raw is None:
    st.error("❌ No se encontró 'SantiagoDB.xlsx'.")
    st.stop()

# --- ESTADO DE SESIÓN ---
if 'filtro_riesgo' not in st.session_state:
    st.session_state.filtro_riesgo = False

# --- FILTROS EN CASCADA ---
with st.sidebar:
    st.image("https://upaep.mx/images/upaep/Logo_UPAEP.svg", width=200)
    st.markdown("### PANEL DE CONTROL")
    
    lista_profes = sorted(df_raw['Nombre catedrático'].unique())
    sel_profes = st.multiselect("Filtrar por Catedrático:", lista_profes)
    df_f = df_raw[df_raw['Nombre catedrático'].isin(sel_profes)] if sel_profes else df_raw
    
    lista_deca = sorted(df_f['Descripción Decanato'].unique())
    sel_deca = st.multiselect("Filtrar por Decanato:", lista_deca)
    if sel_deca: df_f = df_f[df_f['Descripción Decanato'].isin(sel_deca)]
    
    lista_asig = sorted(df_f['Nombre Asignatura'].unique())
    sel_asig = st.multiselect("Filtrar por Asignatura:", lista_asig)
    if sel_asig: df_f = df_f[df_f['Nombre Asignatura'].isin(sel_asig)]

if st.session_state.filtro_riesgo:
    df_f = df_f[df_f['EsRiesgo'] == "SÍ"]

# --- HEADER ---
st.markdown('<p class="main-title">Dashboard Educativo</p>', unsafe_allow_html=True)
st.markdown('<p class="author-tag">by <b>Carlos Osorio y Geovanny Olivares</b></p>', unsafe_allow_html=True)

# --- KPIs SEMAFORIZADOS Y DELIMITADOS ---
def get_kpi_card(label, value, color="#333333"):
    return f"""
    <div class="kpi-card" style="border-left: 10px solid {color};">
        <p class="kpi-label">{label}</p>
        <p class="kpi-value" style="color: {color} !important;">{value}</p>
    </div>
    """

def get_color_nota(val):
    if val >= 9: return "#28a745"
    if val >= 7: return "#ffc107"
    return "#dc3545"

def get_color_pct(val):
    if val >= 80: return "#28a745"
    if val >= 70: return "#ffc107"
    return "#dc3545"

k1, k2, k3, k4 = st.columns(4)
k5, k6, k7, k8 = st.columns(4)

# Fila 1
nota = df_f['CF.'].mean()
k1.markdown(get_kpi_card("Nota Promedio", f"{nota:.2f}", get_color_nota(nota)), unsafe_allow_html=True)

aprob = (df_f['CF.'] >= 6).mean() * 100
k2.markdown(get_kpi_card("% Aprobación", f"{aprob:.1f}%", get_color_pct(aprob)), unsafe_allow_html=True)

faltas = int(df_f['Total_Faltas'].sum())
k3.markdown(get_kpi_card("Faltas Totales", faltas, "#CF091C"), unsafe_allow_html=True)

riesgo_n = len(df_f[df_f['EsRiesgo'] == "SÍ"])
k4.markdown(get_kpi_card("Alumnos en Riesgo", riesgo_n, "#000000"), unsafe_allow_html=True)
with k4:
    if st.button("Ver Riesgo" if not st.session_state.filtro_riesgo else "Ver Todo", key="btn_riesgo"):
        st.session_state.filtro_riesgo = not st.session_state.filtro_riesgo
        st.rerun()

# Fila 2
asis = df_f['%Asis'].mean()
k5.markdown(get_kpi_card("Asistencia Prom.", f"{asis:.1f}%", get_color_pct(asis)), unsafe_allow_html=True)

k6.markdown(get_kpi_card("Total Alumnos", df_f['ID'].nunique(), "#666666"), unsafe_allow_html=True)
k7.markdown(get_kpi_card("Docentes", df_f['Nombre catedrático'].nunique(), "#666666"), unsafe_allow_html=True)
k8.markdown(get_kpi_card("Materias", df_f['Nombre Asignatura'].nunique(), "#666666"), unsafe_allow_html=True)

st.markdown("---")

# --- GRÁFICA DE AUSENTISMO (TEXTO BLANCO SOBRE BARRAS) ---
st.markdown("### 📊 Reporte de Ausentismo por Docente y Parcial")

faltas_data = df_f.groupby('Nombre catedrático')[['F1', 'F2', 'F3']].sum().reset_index()
faltas_plot = faltas_data.melt(id_vars='Nombre catedrático', var_name='Parcial', value_name='Faltas')

fig_faltas = px.bar(faltas_plot, x="Nombre catedrático", y="Faltas", color="Parcial",
                    barmode="group", color_discrete_map={'F1': '#CF091C', 'F2': '#444444', 'F3': '#000000'},
                    template="plotly_white", text_auto=True)

# AJUSTE DE CONTRASTE: Texto blanco en las barras, negro en ejes
fig_faltas.update_traces(textfont_color="white", textposition="inside")
fig_faltas.update_layout(
    font=dict(color="black", size=12),
    legend=dict(font=dict(color="black")),
    xaxis=dict(tickfont=dict(color='black')),
    yaxis=dict(tickfont=dict(color='black')),
    paper_bgcolor='rgba(0,0,0,0)',
    plot_bgcolor='rgba(0,0,0,0)'
)
st.plotly_chart(fig_faltas, use_container_width=True)

# --- GRÁFICA DE DISPERSIÓN (TEXTO BLANCO Y ALTO CONTRASTE) ---
st.markdown("### 🎯 Nota Final vs Asistencia (%)")
# Usamos un fondo oscuro solo para la zona de la gráfica para que resalte el texto blanco
df_f['sz'] = df_f['CF.'].apply(lambda x: 10 if x <= 0 else x * 3).fillna(5)
fig_corr = px.scatter(df_f, x="%Asis", y="CF.", color="Nombre Asignatura", size="sz",
    hover_name="Alumno_Full", template="plotly_dark")
    
# AJUSTE SOLICITADO: Texto blanco para leyenda y valores
fig_corr.update_layout(
        font=dict(color="white"),
        legend=dict(font=dict(color="white"), bgcolor="rgba(0,0,0,0.5)"),
        paper_bgcolor='#333333', # Fondo oscuro para que el texto blanco sea visible
        plot_bgcolor='#222222',
        xaxis=dict(gridcolor='#444444', title_font=dict(color='white'), tickfont=dict(color='white')),
        yaxis=dict(gridcolor='#444444', title_font=dict(color='white'), tickfont=dict(color='white'))
    )
st.plotly_chart(fig_corr, use_container_width=True)

st.markdown("### 🏆 Ranking de Rendimiento por Materia")
ranking = df_f.groupby('Nombre Asignatura')['CF.'].mean().sort_values().reset_index()
fig_rank = px.bar(ranking, x="CF.", y="Nombre Asignatura", orientation='h',
                      color="CF.", color_continuous_scale="Reds", template="simple_white")
fig_rank.update_layout(font=dict(color="black"))
st.plotly_chart(fig_rank, use_container_width=True)

# --- TABLA DETALLE ---
st.markdown("### 📋 Listado de Alumnos")
st.dataframe(df_f[['Alumno_Full', 'Nombre catedrático', 'Nombre Asignatura', 'P1', 'P2', 'P3', 'CF.', 'Total_Faltas']], use_container_width=True)