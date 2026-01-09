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

# --- CONEXIÓN SEGURA A GOOGLE SHEETS ---
@st.cache_data(ttl=600)
def load_data():
    # 1. Recuperar la llave desde Secrets
    json_str = st.secrets["credenciales_json"]
    
    # --- AQUÍ ESTÁ EL ARREGLO ---
    # Usamos strict=False para que perdone los caracteres invisibles del copy-paste
    key_dict = json.loads(json_str, strict=False) 
    
    # 2. Autenticar con Google
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(key_dict, scopes=scopes)
    client = gspread.authorize(creds)
    
    # 3. CONECTAR ARCHIVO FINANCIERO
    # ID del archivo maestro de negocio
    sheet_fin_id = "1ldntONNpWFgXPcF8VINDKzNAhG_vGMdzGEOESM3aLNU" 
    sh_fin = client.open_by_key(sheet_fin_id)
    ws_movs = sh_fin.worksheet("01_Movimientos financieros desde 2026")
    
    # Leer datos financieros
    data_fin = ws_movs.get_all_records()
    df_fin = pd.DataFrame(data_fin)
    
    # Limpieza básica Financiera
    col_monto = "Monto del movimiento (negativo o positivo)"
    if col_monto in df_fin.columns:
        df_fin[col_monto] = df_fin[col_monto].astype(str).str.replace(r'[$,]', '', regex=True)
        df_fin[col_monto] = pd.to_numeric(df_fin[col_monto], errors='coerce').fillna(0)
    
    # 4. CONECTAR BACKLOG (Operativo)
    sheet_ops_id = "1Vl5rhQDi6YooJgjYAF76oOO0aN8rbPtu07giky36wSo"
    sh_ops = client.open_by_key(sheet_ops_id)
    
    consultores = ["Sebastian Saenz", "Alejandra Buriticá", "Alejandra Cárdenas", "Jimmy Peña"]
    all_tasks = []
    
    for consultor in consultores:
        try:
            ws = sh_ops.worksheet(consultor)
            raw_data = ws.get_all_values()
            headers = raw_data[4] # Encabezados en fila 5
            rows = raw_data[5:]   # Datos desde fila 6
            
            temp_df = pd.DataFrame(rows, columns=headers)
            temp_df['Consultor'] = consultor
            
            cols_tiempo = ['Tiempo estimado', 'Tiempo real']
            for col in cols_tiempo:
                if col in temp_df.columns:
                    temp_df[col] = temp_df[col].astype(str).str.replace(',', '.', regex=False)
                    temp_df[col] = pd.to_numeric(temp_df[col], errors='coerce').fillna(0)
            
            all_tasks.append(temp_df)
        except:
            pass
            
    df_ops = pd.concat(all_tasks, ignore_index=True) if all_tasks else pd.DataFrame()

    return df_fin, df_ops

# --- LOGICA DE LA APP ---
try:
    df_fin, df_ops = load_data()
    st.toast("Conexión establecida con goBIG Cloud", icon="🟢")
except Exception as e:
    st.error(f"Error de conexión: {str(e)}")
    st.stop()

# --- SIDEBAR ---
st.sidebar.title("goBIG Intelligence")
st.sidebar.markdown("---")
view_mode = st.sidebar.radio("Dimensiones:", 
    ["1. Financiera (Cash Flow)", 
     "2. Rentabilidad (Clientes)", 
     "3. Operativa (Eficiencia)"])

# --- VISTAS ---

if "Financiera" in view_mode:
    st.title("💰 Financiera: Flujo de Caja Real")
    
    col_monto = "Monto del movimiento (negativo o positivo)"
    if not df_fin.empty and col_monto in df_fin.columns:
        ingresos = df_fin[df_fin[col_monto] > 0][col_monto].sum()
        egresos = df_fin[df_fin[col_monto] < 0][col_monto].sum()
        balance = ingresos + egresos
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Ingresos Totales", f"${ingresos:,.0f}")
        col2.metric("Egresos Totales", f"${egresos:,.0f}")
        col3.metric("Flujo de Caja Neto", f"${balance:,.0f}")
        
        st.markdown("---")
        st.subheader("Movimientos por Centro de Costos")
        if "Centro de costos" in df_fin.columns:
            df_grouped = df_fin.groupby("Centro de costos")[col_monto].sum().reset_index()
            fig = px.bar(df_grouped, x="Centro de costos", y=col_monto, 
                         color=col_monto, color_continuous_scale="RdBu",
                         title="Balance por Cliente")
            fig.update_layout(template="plotly_dark")
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("No se encontraron movimientos financieros.")

elif "Rentabilidad" in view_mode:
    st.title("💎 Rentabilidad por Cliente")
    st.info("🚧 Módulo en construcción: Cruzando Facturación vs Costos")
    st.dataframe(df_ops.head())

elif "Operativa" in view_mode:
    st.title("⚙️ Operativa: Eficiencia del Equipo")
    
    if not df_ops.empty:
        total_horas = df_ops['Tiempo real'].sum()
        st.metric("Total Horas Ejecutadas (2026)", f"{total_horas:.1f} h")
        
        st.subheader("Precisión de Estimaciones")
        df_eff = df_ops.groupby("Consultor")[['Tiempo estimado', 'Tiempo real']].sum().reset_index()
        
        fig_eff = go.Figure()
        fig_eff.add_trace(go.Bar(x=df_eff['Consultor'], y=df_eff['Tiempo estimado'], name='Estimado'))
        fig_eff.add_trace(go.Bar(x=df_eff['Consultor'], y=df_eff['Tiempo real'], name='Real'))
        fig_eff.update_layout(barmode='group', template="plotly_dark")
        st.plotly_chart(fig_eff, use_container_width=True)
