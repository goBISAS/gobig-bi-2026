import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import gspread
from google.oauth2.service_account import Credentials
import json

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="goBIG BI 2026", page_icon="🚀", layout="wide")

# Estilos visuales
st.markdown("""
    <style>
    .main { background-color: #0e1117; }
    .stMetric { background-color: #262730; padding: 15px; border-radius: 5px; border: 1px solid #444; }
    h1, h2, h3 { color: #fff; }
    </style>
    """, unsafe_allow_html=True)

# --- CONEXIÓN SEGURA ---
@st.cache_data(ttl=600)
def load_data():
    # 1. Recuperar llave
    json_str = st.secrets["credenciales_json"]
    key_dict = json.loads(json_str, strict=False)
    
    # 2. Autenticar
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(key_dict, scopes=scopes)
    client = gspread.authorize(creds)
    
    # 3. CONECTAR FINANCIERO (Reemplaza con tus IDs si cambian, pero ya deberían estar bien)
    # Pega aquí tus IDs CORRECTOS que ya buscaste antes
    sheet_fin_id = "1ldntONNpWFgXPcF8VINDKzNAhG_vGMdzGEOESM3aLNU" 
    sh_fin = client.open_by_key(sheet_fin_id)
    ws_movs = sh_fin.worksheet("01_Movimientos financieros desde 2026")
    
    data_fin = ws_movs.get_all_records()
    df_fin = pd.DataFrame(data_fin)
    
    # --- LIMPIEZA INTELIGENTE DE COLUMNAS ---
    # Esto quita espacios al principio y final de los nombres de las columnas
    df_fin.columns = df_fin.columns.str.strip()
    
    # Intentamos encontrar la columna de monto automáticamente
    col_monto_real = None
    posibles_nombres = ["Monto del movimiento", "Monto", "Valor", "Monto del movimiento (negativo o positivo)"]
    
    for col in df_fin.columns:
        for posible in posibles_nombres:
            if posible in col:
                col_monto_real = col
                break
        if col_monto_real: break
    
    # Limpieza de datos numéricos
    if col_monto_real:
        df_fin[col_monto_real] = df_fin[col_monto_real].astype(str).str.replace(r'[$,]', '', regex=True)
        df_fin[col_monto_real] = pd.to_numeric(df_fin[col_monto_real], errors='coerce').fillna(0)
    
    return df_fin, col_monto_real

# --- CARGA ---
try:
    df_fin, col_monto = load_data()
    st.toast("Conexión OK", icon="🟢")
except Exception as e:
    st.error(f"Error: {str(e)}")
    st.stop()

# --- SIDEBAR ---
st.sidebar.title("goBIG Intelligence")
st.sidebar.markdown("---")
view_mode = st.sidebar.radio("Dimensiones:", ["1. Financiera", "2. Rentabilidad", "3. Operativa"])

# --- ZONA DE DIAGNÓSTICO (NUEVO) ---
st.sidebar.markdown("---")
mostrar_diagnostico = st.sidebar.checkbox("🛠️ Modo Diagnóstico")

if mostrar_diagnostico:
    st.warning("🕵️‍♂️ ZONA DE INSPECCIÓN DE DATOS")
    st.write("**Nombres de columnas encontrados:**")
    st.write(list(df_fin.columns))
    st.write(f"**Columna detectada como Monto:** {col_monto}")
    st.write("**Primeras 5 filas de datos:**")
    st.dataframe(df_fin.head())

# --- VISTAS ---
if "Financiera" in view_mode:
    st.title("💰 Financiera: Flujo de Caja Real")
    
    if col_monto:
        ingresos = df_fin[df_fin[col_monto] > 0][col_monto].sum()
        egresos = df_fin[df_fin[col_monto] < 0][col_monto].sum()
        balance = ingresos + egresos
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Ingresos Totales", f"${ingresos:,.0f}")
        col2.metric("Egresos Totales", f"${egresos:,.0f}")
        col3.metric("Flujo de Caja Neto", f"${balance:,.0f}")
        
        # Gráfica
        # Buscamos columna de Centro de Costos de forma flexible
        col_cc = next((c for c in df_fin.columns if "Centro de costos" in c), None)
        
        if col_cc:
            df_grouped = df_fin.groupby(col_cc)[col_monto].sum().reset_index()
            fig = px.bar(df_grouped, x=col_cc, y=col_monto, 
                         color=col_monto, color_continuous_scale="RdBu",
                         title="Balance por Cliente")
            fig.update_layout(template="plotly_dark")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning("No encontré la columna 'Centro de costos'. Revisa el diagnóstico.")
            
    else:
        st.error("🚨 No pude encontrar la columna de Monto. Activa el 'Modo Diagnóstico' en la izquierda para ver los nombres reales.")
