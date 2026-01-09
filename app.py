import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import gspread
from google.oauth2.service_account import Credentials
import json

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="goBIG BI 2026", page_icon="🚀", layout="wide")

# Estilos visuales (Modo oscuro profesional)
st.markdown("""
    <style>
    .main { background-color: #0e1117; }
    .stMetric { background-color: #262730; padding: 15px; border-radius: 5px; border: 1px solid #444; }
    h1, h2, h3 { color: #fff; }
    </style>
    """, unsafe_allow_html=True)

# --- CONEXIÓN SEGURA A GOOGLE SHEETS ---
@st.cache_data(ttl=600) # Se actualiza cada 10 minutos
def load_data():
    # 1. Recuperar la llave desde Secrets
    json_str = st.secrets["credenciales_json"]
    key_dict = json.loads(json_str)
    
    # 2. Autenticar con Google
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(key_dict, scopes=scopes)
    client = gspread.authorize(creds)
    
    # 3. CONECTAR ARCHIVO FINANCIERO
    # ID del archivo maestro de negocio
    sheet_fin_id = "11dntONNpWFgXPcF8VINDKzNAhG_vGMdzGEOESM3aLNU" 
    sh_fin = client.open_by_key(sheet_fin_id)
    ws_movs = sh_fin.worksheet("01_Movimientos financieros desde 2026")
    
    # Leer datos financieros (asumiendo encabezados en fila 1)
    data_fin = ws_movs.get_all_records()
    df_fin = pd.DataFrame(data_fin)
    
    # Limpieza básica Financiera
    # Convertir monto a número (quitando signos $ y comas si existen)
    col_monto = "Monto del movimiento (negativo o positivo)" # Nombre exacto columna C
    if col_monto in df_fin.columns:
        df_fin[col_monto] = df_fin[col_monto].astype(str).str.replace(r'[$,]', '', regex=True)
        df_fin[col_monto] = pd.to_numeric(df_fin[col_monto], errors='coerce').fillna(0)
    
    # 4. CONECTAR BACKLOG (Operativo)
    # ID del archivo de backlog
    sheet_ops_id = "1Vl5rhQDi6YooJgjYAF760000aN8rbPtu07giky36wSo"
    sh_ops = client.open_by_key(sheet_ops_id)
    
    # Lista de consultores (hojas a leer)
    consultores = ["Sebastian Saenz", "Alejandra Buriticá", "Alejandra Cárdenas", "Jimmy Peña"]
    all_tasks = []
    
    for consultor in consultores:
        try:
            ws = sh_ops.worksheet(consultor)
            # Leer datos crudos desde la fila 6 (donde empiezan los datos reales)
            raw_data = ws.get_all_values()
            # La fila 5 del sheet (índice 4 en python) son los encabezados
            headers = raw_data[4] 
            rows = raw_data[5:] # Datos desde fila 6
            
            temp_df = pd.DataFrame(rows, columns=headers)
            temp_df['Consultor'] = consultor # Añadir columna de quién es
            
            # Limpiar columnas de tiempo (Estimado y Real)
            cols_tiempo = ['Tiempo estimado', 'Tiempo real']
            for col in cols_tiempo:
                if col in temp_df.columns:
                    temp_df[col] = temp_df[col].astype(str).str.replace(',', '.', regex=False)
                    temp_df[col] = pd.to_numeric(temp_df[col], errors='coerce').fillna(0)
            
            all_tasks.append(temp_df)
        except:
            pass # Si la hoja no existe o falla, saltar
            
    df_ops = pd.concat(all_tasks, ignore_index=True) if all_tasks else pd.DataFrame()

    return df_fin, df_ops

# --- LOGICA DE LA APP ---
try:
    df_fin, df_ops = load_data()
    st.toast("Datos conectados exitosamente a Google Sheets", icon="🟢")
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
    
    # Calcular KPIs
    col_monto = "Monto del movimiento (negativo o positivo)"
    # Ingresos: números positivos
    ingresos = df_fin[df_fin[col_monto] > 0][col_monto].sum()
    # Egresos: números negativos
    egresos = df_fin[df_fin[col_monto] < 0][col_monto].sum()
    balance = ingresos + egresos # Egresos ya son negativos
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Ingresos Totales", f"${ingresos:,.0f}")
    col2.metric("Egresos Totales", f"${egresos:,.0f}")
    col3.metric("Flujo de Caja Neto", f"${balance:,.0f}")
    
    st.markdown("---")
    st.subheader("Movimientos por Centro de Costos")
    
    # Gráfica de barras por Centro de Costos
    if "Centro de costos" in df_fin.columns:
        df_grouped = df_fin.groupby("Centro de costos")[col_monto].sum().reset_index()
        fig = px.bar(df_grouped, x="Centro de costos", y=col_monto, 
                     color=col_monto, color_continuous_scale="RdBu",
                     title="Balance por Cliente / Centro de Costos")
        fig.update_layout(template="plotly_dark")
        st.plotly_chart(fig, use_container_width=True)
        
    st.caption("Nota: Datos extraídos directamente de la hoja '01_Movimientos financieros'[cite: 33].")

elif "Rentabilidad" in view_mode:
    st.title("💎 Rentabilidad por Cliente")
    st.info("🚧 Módulo cruzando Facturación vs Costos de Nómina (Próximamente con Hoja 02 y 04)")
    
    # Mostrar tabla cruda de backlog como referencia temporal
    st.write("Vista preliminar de actividad registrada:")
    if not df_ops.empty:
        st.dataframe(df_ops[['Consultor', 'Nombre del cliente', 'Tiempo real']].head(10))

elif "Operativa" in view_mode:
    st.title("⚙️ Operativa: Eficiencia del Equipo")
    
    if not df_ops.empty:
        # KPI: Total Horas
        total_horas = df_ops['Tiempo real'].sum()
        st.metric("Total Horas Ejecutadas (2026)", f"{total_horas:.1f} h")
        
        # Gráfica: Estimado vs Real por Consultor
        st.subheader("Precisión de Estimaciones (Ratio de Eficiencia)")
        df_eff = df_ops.groupby("Consultor")[['Tiempo estimado', 'Tiempo real']].sum().reset_index()
        
        fig_eff = go.Figure()
        fig_eff.add_trace(go.Bar(x=df_eff['Consultor'], y=df_eff['Tiempo estimado'], name='Estimado'))
        fig_eff.add_trace(go.Bar(x=df_eff['Consultor'], y=df_eff['Tiempo real'], name='Real'))
        fig_eff.update_layout(barmode='group', template="plotly_dark", title="Estimado vs Real [cite: 60]")
        st.plotly_chart(fig_eff, use_container_width=True)
        
        # Alerta Burnout
        st.subheader("Carga Laboral")
        st.write("Distribución de horas por tipo de tarea:")
        fig_pie = px.pie(df_ops, names='Tipo de tarea', values='Tiempo real', hole=0.4, template="plotly_dark")
        st.plotly_chart(fig_pie)
    else:
        st.warning("No se encontraron datos en el Backlog. Verifica los nombres de las hojas.")
