import streamlit as st
import pandas as pd
import plotly.express as px
import os
from scipy.stats import pearsonr
from google import genai

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(layout="wide", page_title="Dashboard Educativo | UPAEP", page_icon="https://www.upaep.mx/favicon.ico")

# --- CSS: ESTÉTICA UNIFICADA Y ALTO CONTRASTE ---
st.markdown("""
    <style>
    .stApp { background-color: #F5F5F5; }
    [data-testid="stSidebar"] { background-color: #E0E0E0; border-right: 4px solid #CF091C; }
    h1, h2, h3, h4, p, span, label, .stMarkdown { color: #000000 !important; font-family: 'Segoe UI', sans-serif; }
    .kpi-card {
        background-color: #FFFFFF; border: 1px solid #CCCCCC; padding: 15px;
        border-radius: 8px; box-shadow: 2px 2px 5px rgba(0,0,0,0.05);
        text-align: center; margin-bottom: 10px; height: 120px;
        display: flex; flex-direction: column; justify-content: center;
    }
    .kpi-label { font-size: 0.85rem; font-weight: bold; color: #333333 !important; text-transform: uppercase; margin-bottom: 5px; }
    .kpi-value { font-size: 1.8rem; font-weight: 800; margin: 0; }
    div.stButton > button {
        width: 100%; background-color: #CF091C !important; color: white !important;
        border-radius: 5px; border: none; font-weight: bold; transition: 0.3s;
    }
    div.stButton > button:hover { background-color: #000000 !important; transform: scale(1.02); }
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
    df['EsRiesgo'] = df.apply(lambda r: "SÍ" if r['CF.'] < 6 or r['%Asis'] < 80 else "NO", axis=1)
    return df

df_raw = load_data()
if df_raw is None:
    st.error("❌ No se encontró 'SantiagoDB.xlsx'.")
    st.stop()

# --- ESTADO DE SESIÓN (EL CEREBRO DEL AUTO-FILTRADO) ---
if 'filtro_riesgo' not in st.session_state: st.session_state.filtro_riesgo = False
if 'sel_profes' not in st.session_state: st.session_state.sel_profes = []
if 'sel_deca' not in st.session_state: st.session_state.sel_deca = []
if 'sel_asig' not in st.session_state: st.session_state.sel_asig = []
if 'sel_alum' not in st.session_state: st.session_state.sel_alum = [] # Nuevo para IA
if 'ultima_respuesta' not in st.session_state: st.session_state.ultima_respuesta = None

# Listas maestras para que la IA sepa qué puede filtrar
lista_profes_m = sorted(df_raw['Nombre catedrático'].unique())
lista_asig_m = sorted(df_raw['Nombre Asignatura'].unique())
lista_alum_m = sorted(df_raw['Alumno_Full'].unique())

# --- FILTROS EN CASCADA (VINCULADOS A SESSION STATE) ---
with st.sidebar:
    st.image("https://upaep.mx/images/upaep/Logo_UPAEP.svg", width=200)
    st.markdown("### PANEL DE CONTROL")
    
    if st.button("Limpiar Filtros 🧹"):
        st.session_state.sel_profes = []
        st.session_state.sel_deca = []
        st.session_state.sel_asig = []
        st.session_state.sel_alum = []
        st.session_state.filtro_riesgo = False
        st.session_state.ultima_respuesta = None
        st.rerun()

    st.session_state.sel_profes = st.multiselect("Filtrar por Catedrático:", lista_profes_m, default=st.session_state.sel_profes)
    df_f = df_raw[df_raw['Nombre catedrático'].isin(st.session_state.sel_profes)] if st.session_state.sel_profes else df_raw
    
    lista_deca = sorted(df_f['Descripción Decanato'].unique())
    st.session_state.sel_deca = st.multiselect("Filtrar por Decanato:", lista_deca, default=st.session_state.sel_deca)
    if st.session_state.sel_deca: df_f = df_f[df_f['Descripción Decanato'].isin(st.session_state.sel_deca)]
    
    lista_asig = sorted(df_f['Nombre Asignatura'].unique())
    st.session_state.sel_asig = st.multiselect("Filtrar por Asignatura:", lista_asig, default=st.session_state.sel_asig)
    if st.session_state.sel_asig: df_f = df_f[df_f['Nombre Asignatura'].isin(st.session_state.sel_asig)]

    lista_alum = sorted(df_f['Alumno_Full'].unique())
    st.session_state.sel_alum = st.multiselect("Alumno Específico:", lista_alum, default=st.session_state.sel_alum)
    if st.session_state.sel_alum: df_f = df_f[df_f['Alumno_Full'].isin(st.session_state.sel_alum)]

if st.session_state.filtro_riesgo:
    df_f = df_f[df_f['EsRiesgo'] == "SÍ"]

# --- HEADER ---
st.markdown('<p class="main-title">Dashboard Educativo</p>', unsafe_allow_html=True)
st.markdown('<p class="author-tag">by <b>Carlos Osorio y Geovanny Olivares</b></p>', unsafe_allow_html=True)

# --- KPIs SEMAFORIZADOS ---
def get_kpi_card(label, value, color="#333333"):
    return f'<div class="kpi-card" style="border-left: 10px solid {color};"><p class="kpi-label">{label}</p><p class="kpi-value" style="color: {color} !important;">{value}</p></div>'

k1, k2, k3, k4 = st.columns(4)
k5, k6, k7, k8 = st.columns(4)

nota = df_f['CF.'].mean()
k1.markdown(get_kpi_card("Nota Promedio", f"{nota:.2f}", "#28a745" if nota >=9 else "#ffc107" if nota >=7 else "#dc3545"), unsafe_allow_html=True)
aprob = (df_f['CF.'] >= 6).mean() * 100
k2.markdown(get_kpi_card("% Aprobación", f"{aprob:.1f}%", "#28a745" if aprob >=80 else "#ffc107" if aprob >=70 else "#dc3545"), unsafe_allow_html=True)
k3.markdown(get_kpi_card("Faltas Totales", int(df_f['Total_Faltas'].sum()), "#CF091C"), unsafe_allow_html=True)
k4.markdown(get_kpi_card("Alumnos en Riesgo", len(df_f[df_f['EsRiesgo'] == "SÍ"]), "#000000"), unsafe_allow_html=True)
with k4:
    if st.button("Ver Riesgo" if not st.session_state.filtro_riesgo else "Ver Todo", key="btn_riesgo"):
        st.session_state.filtro_riesgo = not st.session_state.filtro_riesgo
        st.rerun()

asis = df_f['%Asis'].mean()
k5.markdown(get_kpi_card("Asistencia Prom.", f"{asis:.1f}%", "#28a745" if asis >=80 else "#ffc107" if asis >=70 else "#dc3545"), unsafe_allow_html=True)
k6.markdown(get_kpi_card("Total Alumnos", df_f['ID'].nunique(), "#666666"), unsafe_allow_html=True)
k7.markdown(get_kpi_card("Docentes", df_f['Nombre catedrático'].nunique(), "#666666"), unsafe_allow_html=True)
k8.markdown(get_kpi_card("Materias", df_f['Nombre Asignatura'].nunique(), "#666666"), unsafe_allow_html=True)

# --- CONFIGURACIÓN DE GEMINI ---
if "GEMINI_API_KEY" in st.secrets:
    client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
else:
    st.warning("⚠️ Configura la GEMINI_API_KEY en los Secrets.")

st.markdown("---")
st.markdown("### 🤖 Consultor Académico Inteligente")
st.caption("Powered by Gemini 2.5 - Control Automático de Dashboard")

with st.form("gemini_rag_form"):
    user_query = st.text_input("Hazle una pregunta a la IA sobre estos datos:", placeholder="Ej: ¿Quién es el alumno con más faltas?")
    submit_button = st.form_submit_button("Consultar y Actualizar Dashboard 🚀")

if submit_button and user_query:
    with st.spinner("Analizando y ajustando gráficas..."):
        contexto_datos = df_f[['Alumno_Full', 'Nombre catedrático', 'Nombre Asignatura', 'CF.', 'Total_Faltas', '%Asis']].to_csv(index=False)
        prompt = f"""
        Eres un asistente analítico experto de la Prepa Santiago UPAEP. 
        CONTEXTO DE DATOS (CSV): {contexto_datos}
        PREGUNTA: {user_query}
        
        INSTRUCCIONES:
        1. Responde de forma ejecutiva.
        2. Si identificas un alumno, profesor o materia específica con problemas, añade al FINAL de tu respuesta exactamente el tag: [TAG: Nombre Exacto].
        """
        try:
            response = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
            full_text = response.text
            
            if "[TAG:" in full_text:
                tag_name = full_text.split("[TAG:")[1].split("]")[0].strip()
                if tag_name in lista_alum_m: st.session_state.sel_alum = [tag_name]
                elif tag_name in lista_profes_m: st.session_state.sel_profes = [tag_name]
                elif tag_name in lista_asig_m: st.session_state.sel_asig = [tag_name]
                
                st.session_state.ultima_respuesta = full_text.split("[TAG:")[0]
                st.rerun()
            else:
                st.session_state.ultima_respuesta = full_text
        except Exception as e:
            st.session_state.ultima_respuesta = "ERROR_429" if "429" in str(e) else f"ERROR: {e}"

if st.session_state.ultima_respuesta:
    if st.session_state.ultima_respuesta == "ERROR_429":
        st.warning("✨ IA en pausa por cuota. Espera 60s.")
    else:
        st.markdown(f"**Respuesta de la IA:**")
        st.info(st.session_state.ultima_respuesta)

st.markdown("---")

# --- GRÁFICA DE AUSENTISMO (A LO ANCHO) ---
st.markdown("### 📊 Reporte de Ausentismo por Docente y Parcial")
faltas_data = df_f.groupby('Nombre catedrático')[['F1', 'F2', 'F3']].sum().reset_index()
faltas_plot = faltas_data.melt(id_vars='Nombre catedrático', var_name='Parcial', value_name='Faltas')
fig_faltas = px.bar(faltas_plot, x="Nombre catedrático", y="Faltas", color="Parcial",
                    barmode="group", color_discrete_map={'F1': '#CF091C', 'F2': '#444444', 'F3': '#000000'},
                    template="plotly_white", text_auto=True)
fig_faltas.update_traces(textfont_color="white", textposition="inside")
fig_faltas.update_layout(font=dict(color="black", size=12), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
st.plotly_chart(fig_faltas, use_container_width=True)

# --- GRÁFICA DE DISPERSIÓN (A LO ANCHO) ---
st.markdown("### 🎯 Nota Final vs Asistencia (%)")
df_f['sz'] = df_f['CF.'].apply(lambda x: 10 if x <= 0 else x * 3).fillna(5)
fig_corr = px.scatter(df_f, x="%Asis", y="CF.", color="Nombre Asignatura", size="sz", hover_name="Alumno_Full", template="plotly_dark")
fig_corr.update_layout(font=dict(color="white"), paper_bgcolor='#333333', plot_bgcolor='#222222')
st.plotly_chart(fig_corr, use_container_width=True)

# --- RANKING (A LO ANCHO) ---
st.markdown("### 🏆 Ranking de Rendimiento por Materia")
ranking = df_f.groupby('Nombre Asignatura')['CF.'].mean().sort_values().reset_index()
fig_rank = px.bar(ranking, x="CF.", y="Nombre Asignatura", orientation='h', color="CF.", color_continuous_scale="Reds", template="simple_white")
st.plotly_chart(fig_rank, use_container_width=True)

# --- TABLA DETALLE (A LO ANCHO) ---
st.markdown("### 📋 Listado de Alumnos")
st.dataframe(df_f[['Alumno_Full', 'Nombre catedrático', 'Nombre Asignatura', 'P1', 'P2', 'P3', 'CF.', 'Total_Faltas']], use_container_width=True)