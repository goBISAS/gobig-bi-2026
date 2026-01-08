import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

# Configuración de la página
st.set_page_config(
    page_title="goBIG BI 2026",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Estilos visuales (Modo oscuro profesional)
st.markdown("""
    <style>
    .main { background-color: #0e1117; }
    .stMetric { background-color: #262730; padding: 15px; border-radius: 5px; }
    </style>
    """, unsafe_allow_html=True)

# --- 1. CARGA DE DATOS (Simulados por ahora) ---
@st.cache_data(ttl=3600)
def load_data():
    # Aquí simulamos tus datos mientras conectamos las hojas reales
    
    # Simulación Datos Financieros
    df_financial = pd.DataFrame({
        'Fecha': pd.date_range(start='2026-01-01', periods=6, freq='M'),
        'Ingresos': [120000000, 115000000, 130000000, 125000000, 140000000, 135000000],
        'Egresos': [80000000, 82000000, 79000000, 85000000, 81000000, 83000000],
        'RST_Provision': [12000000, 11500000, 13000000, 12500000, 14000000, 13500000]
    })
    
    # Simulación Datos Backlog
    df_ops = pd.DataFrame({
        'Consultor': ['Sebastian', 'Alejandra B', 'Alejandra C', 'Jimmy'],
        'Horas_Estimadas': [160, 150, 170, 160],
        'Horas_Reales': [155, 165, 160, 158],
        'Cliente': ['Tienda de Agro', 'Bogoapts', 'H. 93', 'Prospección']
    })
    
    return df_financial, df_ops

# Cargar los datos
try:
    df_fin, df_ops = load_data()
except Exception as e:
    st.error(f"Error: {e}")
    st.stop()

# --- 2. BARRA LATERAL ---
st.sidebar.title("goBIG Intelligence")
view_mode = st.sidebar.radio("Dimensiones:", 
    ["1. Financiera (Cash Flow)", "2. Rentabilidad (Clientes)", 
     "3. Operativa (Eficiencia)", "4. Proyección 2026"])
st.sidebar.info(f"📅 Actualizado: {datetime.now().strftime('%d/%m/%Y')}")

# --- 3. PANTALLAS PRINCIPALES ---

if "Financiera" in view_mode:
    st.title("💰 Financiera: Salud del Negocio")
    col1, col2, col3 = st.columns(3)
    ingresos = df_fin['Ingresos'].sum()
    egresos = df_fin['Egresos'].sum()
    cash_flow = ingresos - egresos
    
    col1.metric("Ingresos YTD", f"${ingresos/1e6:.1f}M", "2.5%")
    col2.metric("Egresos YTD", f"${egresos/1e6:.1f}M", "-1.2%")
    col3.metric("Cash Flow Neto", f"${cash_flow/1e6:.1f}M", "5%")

    st.subheader("Evolución P&L Mensual")
    fig_pl = go.Figure()
    fig_pl.add_trace(go.Bar(x=df_fin['Fecha'], y=df_fin['Ingresos'], name='Ingresos', marker_color='#00CC96'))
    fig_pl.add_trace(go.Bar(x=df_fin['Fecha'], y=df_fin['Egresos'], name='Egresos', marker_color='#EF553B'))
    fig_pl.update_layout(barmode='group', template="plotly_dark", height=400)
    st.plotly_chart(fig_pl, use_container_width=True)

elif "Rentabilidad" in view_mode:
    st.title("💎 Rentabilidad")
    st.subheader("Ranking de Servicios (Simulado)")
    data_heatmap = pd.DataFrame({
        'Servicio': ['BI', 'Mkt 360', 'Ads', 'BI', 'Mkt 360', 'Ads'],
        'Cliente': ['Cliente A', 'Cliente A', 'Cliente B', 'Cliente C', 'Cliente B', 'Cliente C'],
        'Facturacion': [50, 120, 30, 60, 100, 40]
    })
    fig_map = px.density_heatmap(data_heatmap, x="Cliente", y="Servicio", z="Facturacion", 
                                 title="Mapa de Calor", template="plotly_dark")
    st.plotly_chart(fig_map, use_container_width=True)

elif "Operativa" in view_mode:
    st.title("⚙️ Operativa")
    st.subheader("Eficiencia por Consultor")
    fig_ops = px.bar(df_ops, x='Consultor', y=['Horas_Estimadas', 'Horas_Reales'], 
                     barmode='group', template="plotly_dark")
    st.plotly_chart(fig_ops, use_container_width=True)

elif "Proyección" in view_mode:
    st.title("🔮 Visión 2026")
    st.info("Módulo de proyecciones en construcción...")
