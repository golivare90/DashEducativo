import streamlit as st
import pandas as pd
import plotly.express as px
import os
from google import genai
import smtplib, io, re, datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from fpdf import FPDF

# --- CONFIGURACIÓN DE PÁGINA (FAVICON UPAEP) ---
st.set_page_config(layout="wide", page_title="Dashboard Educativo | UPAEP", page_icon="https://www.upaep.mx/favicon.ico")

# --- CSS: ESTÉTICA Y TOOLTIPS CREATIVOS ---
st.markdown("""
    <style>
    .stApp { background-color: #F5F5F5; }
    [data-testid="stSidebar"] { background-color: #E0E0E0; border-right: 4px solid #CF091C; }
    h1, h2, h3, h4, p, span, label, .stMarkdown { color: #000000 !important; font-family: 'Segoe UI', sans-serif; }
    
    /* TARJETAS KPI */
    .kpi-card {
        background-color: #FFFFFF; border: 1px solid #CCCCCC; padding: 15px;
        border-radius: 8px; box-shadow: 2px 2px 5px rgba(0,0,0,0.05);
        text-align: center; margin-bottom: 10px; height: 120px;
        display: flex; flex-direction: column; justify-content: center;
        position: relative;
    }
    
    /* TOOLTIP CREATIVO */
    .tooltip {
        position: absolute; top: 10px; right: 10px;
        display: inline-block; cursor: pointer;
        background-color: #EEEEEE; border-radius: 50%;
        width: 20px; height: 20px; font-size: 14px; line-height: 20px;
        color: #666; font-weight: bold;
    }
    .tooltip .tooltiptext {
        visibility: hidden; width: 220px; background-color: #333;
        color: #fff; text-align: left; border-radius: 6px;
        padding: 10px; position: absolute; z-index: 100;
        bottom: 125%; left: 50%; margin-left: -110px;
        opacity: 0; transition: opacity 0.3s;
        font-size: 0.75rem; font-weight: normal; line-height: 1.2rem;
    }
    .tooltip:hover .tooltiptext { visibility: visible; opacity: 1; }
    
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

# --- ESTADO DE SESIÓN ---
if 'filtro_riesgo' not in st.session_state: st.session_state.filtro_riesgo = False
if 'filtro_zona_gris' not in st.session_state: st.session_state.filtro_zona_gris = False
if 'sel_profes' not in st.session_state: st.session_state.sel_profes = []
if 'sel_deca' not in st.session_state: st.session_state.sel_deca = []
if 'sel_asig' not in st.session_state: st.session_state.sel_asig = []
if 'sel_alum' not in st.session_state: st.session_state.sel_alum = []
if 'ultima_respuesta' not in st.session_state: st.session_state.ultima_respuesta = None

lista_profes_m = sorted(df_raw['Nombre catedrático'].unique())
lista_asig_m = sorted(df_raw['Nombre Asignatura'].unique())
lista_alum_m = sorted(df_raw['Alumno_Full'].unique())

# --- FILTROS SIDEBAR ---
with st.sidebar:
    st.image("https://upaep.mx/images/upaep/Logo_UPAEP.svg", width=200)
    st.markdown("### PANEL DE CONTROL")
    if st.button("Limpiar Filtros 🧹"):
        st.session_state.sel_profes, st.session_state.sel_deca, st.session_state.sel_asig, st.session_state.sel_alum = [], [], [], []
        st.session_state.filtro_riesgo, st.session_state.filtro_zona_gris = False, False
        st.session_state.ultima_respuesta = None
        st.rerun()

    # -- Cross-filtering: opciones de cada filtro dependen de los demás activos --
    def _apply(df, excl=None):
        if excl != 'profes' and st.session_state.sel_profes:
            df = df[df['Nombre catedrático'].isin(st.session_state.sel_profes)]
        if excl != 'deca' and st.session_state.sel_deca:
            df = df[df['Descripción Decanato'].isin(st.session_state.sel_deca)]
        if excl != 'asig' and st.session_state.sel_asig:
            df = df[df['Nombre Asignatura'].isin(st.session_state.sel_asig)]
        if excl != 'alum' and st.session_state.sel_alum:
            df = df[df['Alumno_Full'].isin(st.session_state.sel_alum)]
        return df

    opt_profes = sorted(_apply(df_raw, excl='profes')['Nombre catedrático'].unique())
    sel_p = [v for v in st.session_state.sel_profes if v in opt_profes]
    st.session_state.sel_profes = st.multiselect("Filtrar por Catedrático:", opt_profes, default=sel_p)

    opt_deca = sorted(_apply(df_raw, excl='deca')['Descripción Decanato'].unique())
    sel_d = [v for v in st.session_state.sel_deca if v in opt_deca]
    st.session_state.sel_deca = st.multiselect("Filtrar por Decanato:", opt_deca, default=sel_d)

    opt_asig = sorted(_apply(df_raw, excl='asig')['Nombre Asignatura'].unique())
    sel_a = [v for v in st.session_state.sel_asig if v in opt_asig]
    st.session_state.sel_asig = st.multiselect("Filtrar por Asignatura:", opt_asig, default=sel_a)

    opt_alum = sorted(_apply(df_raw, excl='alum')['Alumno_Full'].unique())
    sel_al = [v for v in st.session_state.sel_alum if v in opt_alum]
    st.session_state.sel_alum = st.multiselect("Alumno Específico:", opt_alum, default=sel_al)

# df_f: intersección de todos los filtros
df_f = _apply(df_raw)
if st.session_state.filtro_riesgo: df_f = df_f[df_f['EsRiesgo'] == "SÍ"]
if st.session_state.filtro_zona_gris:
    df_f = df_f[(((df_f['CF.'] >= 6) & (df_f['CF.'] <= 7)) | ((df_f['%Asis'] >= 80) & (df_f['%Asis'] <= 85)))]

# --- HEADER ---
st.markdown('<p class="main-title">Dashboard Educativo</p>', unsafe_allow_html=True)
st.markdown('<p class="author-tag">by <b>Carlos Osorio y Geovanny Olivares</b></p>', unsafe_allow_html=True)

# --- FUNCIÓN KPI CON TOOLTIP ---
def get_kpi_card(label, value, color, calc, desc, ranges):
    return f"""
    <div class="kpi-card" style="border-left: 10px solid {color};">
        <div class="tooltip">i
            <span class="tooltiptext">
                <b>Definición:</b> {desc}<br><br>
                <b>Cálculo:</b> {calc}<br><br>
                <b>Semáforo:</b><br>{ranges}
            </span>
        </div>
        <p class="kpi-label">{label}</p>
        <p class="kpi-value" style="color: {color} !important;">{value}</p>
    </div>
    """

# --- CÁLCULOS ---
total_est = df_f['ID'].nunique()
riesgo_n = len(df_f[df_f['EsRiesgo'] == "SÍ"])
retencion = ((total_est - riesgo_n) / total_est * 100) if total_est > 0 else 0
zona_gris_n = len(df_f[((df_f['CF.'] >= 6) & (df_f['CF.'] <= 7)) | ((df_f['%Asis'] >= 80) & (df_f['%Asis'] <= 85))])
nota_prom = df_f['CF.'].mean()
aprob_pct = (df_f['CF.'] >= 6).mean() * 100

# --- FILA 1 ---
k1, k2, k3, k4 = st.columns(4)
k1.markdown(get_kpi_card("Nota Promedio", f"{nota_prom:.2f}", "#28a745" if nota_prom >=9 else "#ffc107" if nota_prom >=7 else "#dc3545", 
                        "Promedio simple de CF.", "Nivel de aprovechamiento académico.", "🟢 >=9 | 🟡 >=7 | 🔴 <7"), unsafe_allow_html=True)
k2.markdown(get_kpi_card("% Aprobación", f"{aprob_pct:.1f}%", "#28a745" if aprob_pct >=80 else "#dc3545",
                        "Count(CF >= 6) / Total", "Relación de éxito vs reprobación.", "🟢 >=80% | 🔴 <80%"), unsafe_allow_html=True)
k3.markdown(get_kpi_card("Faltas Totales", int(df_f['Total_Faltas'].sum()), "#CF091C",
                        "Sum(F1 + F2 + F3)", "Acumulado de inasistencias.", "🔴 Crítico si supera 15% del total hrs."), unsafe_allow_html=True)
k4.markdown(get_kpi_card("Alumnos en Riesgo", riesgo_n, "#000000",
                        "CF < 6 OR Asis < 80%", "Estudiantes que requieren intervención inmediata.", "🔴 Cualquier coincidencia es Riesgo."), unsafe_allow_html=True)
with k4:
    if st.button("Ver Riesgo ✓" if st.session_state.filtro_riesgo else "Ver Riesgo", key="btn_riesgo"):
        st.session_state.filtro_riesgo = not st.session_state.filtro_riesgo
        st.rerun()

# --- FILA 2 ---
k5, k6, k7, k8 = st.columns(4)
asis_p = df_f['%Asis'].mean()
k5.markdown(get_kpi_card("Asistencia Prom.", f"{asis_p:.1f}%", "#28a745" if asis_p >=80 else "#dc3545",
                        "Media de %Asis", "Constancia de presencia en aula.", "🟢 >=80% | 🔴 <80%"), unsafe_allow_html=True)
k6.markdown(get_kpi_card("Total Alumnos", total_est, "#666666", "Count(ID) únicos", "Población estudiantil actual.", "N/A"), unsafe_allow_html=True)
k7.markdown(get_kpi_card("Docentes", df_f['Nombre catedrático'].nunique(), "#666666", "Count(Catedrático) únicos", "Cuerpo docente involucrado.", "N/A"), unsafe_allow_html=True)
k8.markdown(get_kpi_card("Materias", df_f['Nombre Asignatura'].nunique(), "#666666", "Count(Materia) únicos", "Diversidad de oferta académica.", "N/A"), unsafe_allow_html=True)

# --- FILA 3 ---
k9, k10, k11, k12 = st.columns(4)
k9.markdown(get_kpi_card("Índice Retención", f"{retencion:.1f}%", "#28a745" if retencion >=95 else "#ffc107",
                        "(Total - Riesgo) / Total", "Salud institucional contra la deserción.", "🟢 >=95% | 🟡 >=85% | 🔴 <85%"), unsafe_allow_html=True)
k10.markdown(get_kpi_card("Zona Gris", zona_gris_n, "#007bff",
                         "6 <= CF <= 7 OR 80 <= Asis <= 85", "Alumnos en el límite preventivo.", "🔵 Foco de monitoreo preventivo."), unsafe_allow_html=True)
with k10:
    if st.button("Ver Zona Gris ✓" if st.session_state.filtro_zona_gris else "Ver Zona Gris", key="btn_gris"):
        st.session_state.filtro_zona_gris = not st.session_state.filtro_zona_gris
        st.rerun()
k11.markdown(get_kpi_card("Eficiencia", f"{(df_f['CF.'] >= 6).mean()*100:.1f}%", "#666666", "Aprobados / Total", "Productividad del proceso de enseñanza.", "N/A"), unsafe_allow_html=True)
k12.markdown(get_kpi_card("Decanatos", df_f['Descripción Decanato'].nunique(), "#666666", "Count(Decanato) únicos", "Alcance administrativo.", "N/A"), unsafe_allow_html=True)

# --- HELPERS PDF ---
def _hex_to_rgb(h):
    h = h.lstrip('#')
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

def _md_to_clean(texto):
    """Convierte markdown básico a texto limpio para FPDF."""
    texto = re.sub(r'\*\*(.+?)\*\*', r'\1', texto)
    texto = re.sub(r'\*(.+?)\*', r'\1', texto)
    texto = re.sub(r'#{1,6}\s?', '', texto)
    return texto

def build_pdf(texto, figuras, kpis, filtros):
    """Genera PDF con portada, KPIs, análisis IA y gráficas."""
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    # -- Portada --
    pdf.add_page()
    pdf.set_fill_color(207, 9, 28)
    pdf.rect(0, 0, 210, 45, 'F')
    pdf.set_font("Helvetica", "B", 22)
    pdf.set_text_color(255, 255, 255)
    pdf.set_xy(10, 10)
    pdf.cell(0, 10, "Dashboard Educativo UPAEP", ln=True)
    pdf.set_font("Helvetica", "", 12)
    pdf.set_xy(10, 26)
    pdf.cell(0, 8, f"Generado: {datetime.datetime.now().strftime('%d/%m/%Y %H:%M')}", ln=True)
    pdf.set_text_color(0, 0, 0)
    # -- Filtros aplicados --
    pdf.set_xy(10, 52)
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 7, "Filtros aplicados:", ln=True)
    pdf.set_font("Helvetica", "", 10)
    for k, v in filtros.items():
        pdf.cell(0, 6, f"  {k}: {v}", ln=True)
    # -- KPIs como tarjetas --
    pdf.ln(4)
    pdf.set_fill_color(240, 240, 240)
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(0, 8, "  Indicadores Clave (KPIs):", ln=True, fill=True)
    pdf.ln(4)
    CARD_W, CARD_H, GAP, BORD = 92, 22, 6, 4
    for i, (label, value, color) in enumerate(kpis):
        col = i % 2
        if col == 0:
            row_y = pdf.get_y()
        x = 10 + col * (CARD_W + GAP)
        r, g, b = _hex_to_rgb(color)
        pdf.set_fill_color(248, 248, 248)
        pdf.rect(x, row_y, CARD_W, CARD_H, 'F')
        pdf.set_fill_color(r, g, b)
        pdf.rect(x, row_y, BORD, CARD_H, 'F')
        pdf.set_font("Helvetica", "B", 7)
        pdf.set_text_color(80, 80, 80)
        pdf.set_xy(x + BORD + 2, row_y + 3)
        pdf.cell(CARD_W - BORD - 2, 5, label.upper().encode('latin-1', 'replace').decode('latin-1'))
        pdf.set_font("Helvetica", "B", 13)
        pdf.set_text_color(r, g, b)
        pdf.set_xy(x + BORD + 2, row_y + 10)
        pdf.cell(CARD_W - BORD - 2, 9, str(value).encode('latin-1', 'replace').decode('latin-1'))
        pdf.set_text_color(0, 0, 0)
        if col == 1 or i == len(kpis) - 1:
            pdf.set_y(row_y + CARD_H + 4)
    # -- Análisis IA --
    if texto:
        pdf.ln(4)
        pdf.set_fill_color(240, 240, 240)
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(0, 8, "  Análisis del Consultor IA", ln=True, fill=True)
        pdf.set_font("Helvetica", "", 10)
        limpio = _md_to_clean(texto)
        for linea in limpio.split('\n'):
            linea_enc = linea.encode('latin-1', 'replace').decode('latin-1')
            pdf.set_x(10)
            pdf.multi_cell(190, 6, linea_enc)
    # -- Gráficas --
    if figuras:
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 13)
        pdf.set_fill_color(207, 9, 28)
        pdf.set_text_color(255, 255, 255)
        pdf.cell(0, 9, "  Visualizaciones", ln=True, fill=True)
        pdf.set_text_color(0, 0, 0)
        for titulo, fig in figuras:
            img_buf = io.BytesIO()
            fig.write_image(img_buf, format="png", width=900, height=420, scale=1.5)
            img_buf.seek(0)
            pdf.ln(4)
            pdf.set_font("Helvetica", "B", 10)
            pdf.cell(0, 7, titulo, ln=True)
            pdf.image(img_buf, x=10, w=185)
            pdf.ln(3)
    return bytes(pdf.output())

def enviar_correo(destinatario, pdf_bytes, asunto):
    msg = MIMEMultipart()
    msg['From'] = st.secrets["EMAIL_SENDER"]
    msg['To'] = destinatario
    msg['Subject'] = asunto
    msg.attach(MIMEText("Adjunto encontrarás el reporte generado desde el Dashboard Educativo UPAEP.", 'plain'))
    part = MIMEBase('application', 'octet-stream')
    part.set_payload(pdf_bytes)
    encoders.encode_base64(part)
    part.add_header('Content-Disposition', 'attachment; filename="reporte_UPAEP.pdf"')
    msg.attach(part)
    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
        server.login(st.secrets["EMAIL_SENDER"], st.secrets["EMAIL_PASSWORD"])
        server.sendmail(st.secrets["EMAIL_SENDER"], destinatario, msg.as_string())

# --- MODAL EXPORTAR RESPUESTA IA ---
@st.dialog("📄 Reporte IA — Dashboard UPAEP", width="large")
def modal_exportar(texto, figuras, kpis, filtros):
    # Renderizar respuesta con HTML formateado
    html_resp = texto.replace('\n', '<br>')
    # Negritas **texto**
    html_resp = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html_resp)
    # Encabezados ###
    html_resp = re.sub(r'#{3}\s?(.+?)(<br>|$)', r'<h4 style="color:#CF091C;margin:8px 0 4px">\1</h4>', html_resp)
    html_resp = re.sub(r'#{2}\s?(.+?)(<br>|$)', r'<h3 style="color:#CF091C;margin:10px 0 4px">\1</h3>', html_resp)
    html_resp = re.sub(r'#{1}\s?(.+?)(<br>|$)', r'<h2 style="color:#CF091C;margin:12px 0 4px">\1</h2>', html_resp)
    st.markdown(f"""
    <div style="background:#fff;border-left:6px solid #CF091C;border-radius:8px;
                padding:20px 24px;box-shadow:0 2px 8px rgba(0,0,0,0.10);
                font-family:'Segoe UI',sans-serif;font-size:0.97rem;
                line-height:1.7;color:#222;max-height:340px;overflow-y:auto;">
        <div style="font-size:0.78rem;color:#888;margin-bottom:10px;text-transform:uppercase;letter-spacing:1px;">
            🤖 Análisis del Consultor Académico Inteligente
        </div>
        {html_resp}
    </div>
    """, unsafe_allow_html=True)
    st.markdown("---")
    # Generar PDF en memoria para preview y descarga
    pdf_bytes = build_pdf(texto, figuras, kpis, filtros)
    c1, c2 = st.columns(2)
    with c1:
        st.download_button("⬇️ Descargar PDF", data=pdf_bytes,
                           file_name="reporte_UPAEP.pdf", mime="application/pdf",
                           use_container_width=True)
    with c2:
        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    st.markdown("---")
    st.markdown("##### 📧 Enviar por correo")
    destinatario = st.text_input("Correo destinatario:", placeholder="ejemplo@upaep.mx")
    if st.button("📨 Enviar reporte por correo", use_container_width=True):
        if not destinatario or "@" not in destinatario:
            st.warning("⚠️ Ingresa un correo válido.")
        else:
            with st.spinner("Enviando..."):
                try:
                    enviar_correo(destinatario, pdf_bytes, "Análisis IA - Dashboard UPAEP")
                    st.success(f"✅ Correo enviado correctamente a **{destinatario}**")
                    st.balloons()
                except Exception as e:
                    st.error(f"❌ Error al enviar: {e}")

# --- MODAL EXPORTAR SOLO GRÁFICAS ---
@st.dialog("📊 Exportar Reporte de Gráficas", width="large")
def modal_graficas(figuras, kpis, filtros):
    st.markdown("Exporta las **gráficas actuales**, KPIs y filtros aplicados a PDF o correo.")
    st.markdown("---")
    pdf_bytes = build_pdf(None, figuras, kpis, filtros)
    c1, c2 = st.columns(2)
    with c1:
        st.download_button("⬇️ Descargar PDF", data=pdf_bytes,
                           file_name="reporte_graficas_UPAEP.pdf", mime="application/pdf",
                           use_container_width=True)
    st.markdown("---")
    st.markdown("##### 📧 Enviar por correo")
    destinatario = st.text_input("Correo destinatario:", placeholder="ejemplo@upaep.mx", key="dest_graf")
    if st.button("📨 Enviar reporte por correo", use_container_width=True, key="btn_send_graf"):
        if not destinatario or "@" not in destinatario:
            st.warning("⚠️ Ingresa un correo válido.")
        else:
            with st.spinner("Enviando..."):
                try:
                    enviar_correo(destinatario, pdf_bytes, "Reporte Gráficas - Dashboard UPAEP")
                    st.success(f"✅ Correo enviado correctamente a **{destinatario}**")
                    st.balloons()
                except Exception as e:
                    st.error(f"❌ Error al enviar: {e}")

# --- PRE-CÁLCULO DE FIGURAS (necesario antes del bloque Gemini) ---
heatmap_data = df_f.groupby('Nombre Asignatura')[['P1', 'P2', 'P3']].mean()
fig_h = px.imshow(heatmap_data, text_auto=".1f", aspect="auto", color_continuous_scale="RdYlGn", template="plotly_white")
fig_box = px.box(df_f, x="Nombre Asignatura", y="CF.", color="Nombre Asignatura", template="plotly_white")
faltas_data = df_f.groupby('Nombre catedrático')[['F1', 'F2', 'F3']].sum().reset_index()
faltas_plot = faltas_data.melt(id_vars='Nombre catedrático', var_name='Parcial', value_name='Faltas')
fig_f = px.bar(faltas_plot, x="Nombre catedrático", y="Faltas", color="Parcial", barmode="group",
             color_discrete_map={'F1': '#CF091C', 'F2': '#444444', 'F3': '#000000'}, template="plotly_white", text_auto=True)
df_f['sz'] = df_f['CF.'].apply(lambda x: 10 if x <= 0 else x * 3).fillna(5)
fig_c = px.scatter(df_f, x="%Asis", y="CF.", color="Nombre Asignatura", size="sz", hover_name="Alumno_Full", template="plotly_dark")
fig_c.update_layout(font=dict(color="white"), paper_bgcolor='#333333', plot_bgcolor='#222222')

# --- CONSULTOR GEMINI CON FAILOVER ESTRATÉGICO ---
if "GEMINI_API_KEY" in st.secrets:
    client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
    st.markdown("---")
    st.markdown("### 🤖 Consultor Académico Inteligente")
    
    with st.form("gemini_form"):
        user_query = st.text_input("Hazle una pregunta a la IA:", placeholder="Ej: ¿Qué materia tiene más alumnos en zona gris?")
        submit = st.form_submit_button("Consultar y Ajustar Dashboard 🚀")

    if submit and user_query:
        with st.spinner("Analizando con resiliencia de Cloud Architect..."):
            contexto = df_f[['Alumno_Full', 'Nombre catedrático', 'Nombre Asignatura', 'CF.', 'Total_Faltas', '%Asis', 'P1', 'P2', 'P3']].to_csv(index=False)
            prompt = f"Analista UPAEP. Datos: {contexto}. Pregunta: {user_query}. Si hay foco, añade al final [TAG: Nombre Exacto]."
            
            # Stack de modelos (Prioridad según doctor.py)
            model_stack = ['gemini-2.5-flash', 'gemini-2.0-flash', 'gemini-2.0-flash-lite', 'gemini-flash-latest']
            response = None
            
            for model_name in model_stack:
                try:
                    # Intento de ejecución con el modelo actual
                    response = client.models.generate_content(model=model_name, contents=prompt)
                    break  # Si tiene éxito, rompemos el loop
                except Exception as e:
                    error_msg = str(e).upper()
                    # Si es saturación o cuota, intentamos el que sigue
                    if any(x in error_msg for x in ["503", "UNAVAILABLE", "429", "RESOURCE_EXHAUSTED"]):
                        continue 
                    else:
                        st.session_state.ultima_respuesta = f"Error crítico en {model_name}: {e}"
                        break

            if response:
                txt = response.text
                if "[TAG:" in txt:
                    tag = txt.split("[TAG:")[1].split("]")[0].strip()
                    # Lógica de filtrado automático
                    if tag in lista_alum_m: st.session_state.sel_alum = [tag]
                    elif tag in lista_profes_m: st.session_state.sel_profes = [tag]
                    elif tag in lista_asig_m: st.session_state.sel_asig = [tag]
                    
                    st.session_state.ultima_respuesta = txt.split("[TAG:")[0]
                    st.rerun()
                else:
                    st.session_state.ultima_respuesta = txt
            elif not st.session_state.ultima_respuesta:
                st.session_state.ultima_respuesta = "⚠️ Todos los modelos de Google están saturados en este momento."

    if st.session_state.ultima_respuesta:
        st.info(st.session_state.ultima_respuesta)
        if st.button("📄 Exportar / Enviar por correo"):
            _kpis_snap = [
                ("Nota Promedio", f"{nota_prom:.2f}", "#28a745" if nota_prom >= 9 else "#ffc107" if nota_prom >= 7 else "#dc3545"),
                ("% Aprobación", f"{aprob_pct:.1f}%", "#28a745" if aprob_pct >= 80 else "#dc3545"),
                ("Alumnos en Riesgo", riesgo_n, "#CF091C"),
                ("Asistencia Prom.", f"{asis_p:.1f}%", "#28a745" if asis_p >= 80 else "#dc3545"),
                ("Total Alumnos", total_est, "#666666"),
                ("Índice Retención", f"{retencion:.1f}%", "#28a745" if retencion >= 95 else "#ffc107"),
                ("Zona Gris", zona_gris_n, "#007bff"),
                ("Eficiencia", f"{(df_f['CF.'] >= 6).mean()*100:.1f}%", "#666666"),
            ]
            _filtros_snap = {"Catedrático": ", ".join(st.session_state.sel_profes) or "Todos",
                             "Decanato": ", ".join(st.session_state.sel_deca) or "Todos",
                             "Asignatura": ", ".join(st.session_state.sel_asig) or "Todas",
                             "Alumno": ", ".join(st.session_state.sel_alum) or "Todos"}
            _figs_snap = [("Mapa de Calor: Desempeño por Materia y Parcial", fig_h),
                          ("Dispersión de Notas", fig_box),
                          ("Ausentismo por Docente", fig_f),
                          ("Nota Final vs Asistencia", fig_c)]
            modal_exportar(st.session_state.ultima_respuesta, _figs_snap, _kpis_snap, _filtros_snap)

else:
    st.error("Falta API Key en los Secrets de Streamlit.")

st.markdown("---")

# --- GRÁFICAS A LO ANCHO CON POPOVERS DE INFO ---

# 1. HEATMAP
st.markdown("### 🌡️ Mapa de Calor: Desempeño por Materia y Parcial")
with st.popover("Explicación del Heatmap ℹ️"):
    st.write("**¿Qué mide?** El promedio de notas por parcial (P1, P2, P3) de cada materia.")
    st.write("**Cálculo:** Mean(P1, P2, P3) agrupado por Asignatura.")
    st.write("**Utilidad:** Detectar si el rendimiento de un grupo cae en un parcial específico (ej. P3) para intervenir.")
st.plotly_chart(fig_h, use_container_width=True)

# 2. BOXPLOT
st.markdown("### 📦 Dispersión de Notas (Caja y Brazos)")
with st.popover("Explicación del Boxplot ℹ️"):
    st.write("**¿Qué mide?** La consistencia académica. La 'caja' es el 50% central de los alumnos.")
    st.write("**Cálculo:** Cuartiles de la Calificación Final (CF).")
    st.write("**Utilidad:** Si la caja es muy larga, el grupo es muy desigual. Si hay puntos fuera (outliers), son casos excepcionales.")
st.plotly_chart(fig_box, use_container_width=True)

# 3. AUSENTISMO
st.markdown("### 📊 Reporte de Ausentismo por Docente")
with st.popover("Explicación de Ausentismo ℹ️"):
    st.write("**¿Qué mide?** Total de faltas acumuladas por profesor.")
    st.write("**Cálculo:** Suma de F1+F2+F3 agrupado por Catedrático.")
    st.write("**Utilidad:** Identificar si hay docentes con una tasa de inasistencia inusual en sus alumnos.")
st.plotly_chart(fig_f, use_container_width=True)

# 4. DISPERSIÓN
st.markdown("### 🎯 Nota Final vs Asistencia (%)")
with st.popover("Explicación de Correlación ℹ️"):
    st.write("**¿Qué mide?** La relación directa entre ir a clases y aprobar.")
    st.write("**Cálculo:** Dispersión XY (Asistencia vs CF).")
    st.write("**Utilidad:** Visualizar si el ausentismo es la causa principal de las notas bajas.")
st.plotly_chart(fig_c, use_container_width=True)

# 5. TABLA
st.markdown("### 📋 Listado Detallado")
st.dataframe(df_f[['Alumno_Full', 'Nombre catedrático', 'Nombre Asignatura', 'CF.', 'Total_Faltas', '%Asis']], use_container_width=True)

# --- BOTÓN EXPORTAR SOLO GRÁFICAS ---
st.markdown("---")
if st.button("📊 Exportar Gráficas + KPIs a PDF / Correo", use_container_width=True):
    _kpis_snap = [
        ("Nota Promedio", f"{nota_prom:.2f}", "#28a745" if nota_prom >= 9 else "#ffc107" if nota_prom >= 7 else "#dc3545"),
        ("% Aprobación", f"{aprob_pct:.1f}%", "#28a745" if aprob_pct >= 80 else "#dc3545"),
        ("Alumnos en Riesgo", riesgo_n, "#CF091C"),
        ("Asistencia Prom.", f"{asis_p:.1f}%", "#28a745" if asis_p >= 80 else "#dc3545"),
        ("Total Alumnos", total_est, "#666666"),
        ("Índice Retención", f"{retencion:.1f}%", "#28a745" if retencion >= 95 else "#ffc107"),
        ("Zona Gris", zona_gris_n, "#007bff"),
        ("Eficiencia", f"{(df_f['CF.'] >= 6).mean()*100:.1f}%", "#666666"),
    ]
    _filtros_snap = {"Catedrático": ", ".join(st.session_state.sel_profes) or "Todos",
                     "Decanato": ", ".join(st.session_state.sel_deca) or "Todos",
                     "Asignatura": ", ".join(st.session_state.sel_asig) or "Todas",
                     "Alumno": ", ".join(st.session_state.sel_alum) or "Todos"}
    _figs_snap = [("Mapa de Calor: Desempeño por Materia y Parcial", fig_h),
                  ("Dispersión de Notas", fig_box),
                  ("Ausentismo por Docente", fig_f),
                  ("Nota Final vs Asistencia", fig_c)]
    modal_graficas(_figs_snap, _kpis_snap, _filtros_snap)