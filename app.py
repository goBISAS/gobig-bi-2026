import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import gspread
from google.oauth2.service_account import Credentials
import json

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="goBIG BI 2026", page_icon="🚀", layout="wide")

# Estilos CSS Profesionales
st.markdown("""
    <style>
    .main { background-color: #0e1117; }
    .stMetric { background-color: #262730; padding: 15px; border-radius: 5px; border: 1px solid #444; }
    h1, h2, h3 { color: #fff; }
    </style>
    """, unsafe_allow_html=True)

# --- FUNCIÓN DE LIMPIEZA DE MONEDA (LA JOYA DE LA CORONA) ---
def limpiar_moneda_colombia(serie):
    """Convierte formatos colombianos ($ 1.000.000,00) a números Python puros."""
    serie = serie.astype(str)
    serie = serie.str.replace(r'[$\s]', '', regex=True) # Quitar $ y espacios
    serie = serie.str.replace('.', '', regex=False)     # Quitar puntos de mil
    serie = serie.str.replace(',', '.', regex=False)    # Cambiar coma por punto
    return pd.to_numeric(serie, errors='coerce').fillna(0)

# --- MOTOR DE DATOS ---
@st.cache_data(ttl=600)
def load_data(fin_id, ops_id):
    # 1. Autenticación Segura
    json_str = st.secrets["credenciales_json"]
    key_dict = json.loads(json_str, strict=False)
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(key_dict, scopes=scopes)
    client = gspread.authorize(creds)
    
    # 2. CARGAR FINANCIERO
    sh_fin = client.open_by_key(fin_id)
    ws_movs = sh_fin.worksheet("01_Movimientos financieros desde 2026")
    df_fin = pd.DataFrame(ws_movs.get_all_records())
    
    # Limpieza Financiera
    df_fin.columns = df_fin.columns.str.strip() # Limpiar nombres de columnas
    
    # Detección automática de la columna Monto
    col_monto = None
    possible_names = ["Monto del movimiento", "Monto", "Valor", "Monto del movimiento (negativo o positivo)"]
    for col in df_fin.columns:
        for name in possible_names:
            if name in col:
                col_monto = col
                break
        if col_monto: break
            
    if col_monto:
        df_fin[col_monto] = limpiar_moneda_colombia(df_fin[col_monto])

    # 3. CARGAR BACKLOG (OPERATIVA) - ¡REACTIVADO!
    sh_ops = client.open_by_key(ops_id)
    consultores = ["Sebastian Saenz", "Alejandra Buriticá", "Alejandra Cárdenas", "Jimmy Peña"]
    all_tasks = []
    
    for consultor in consultores:
        try:
            ws = sh_ops.worksheet(consultor)
            raw_data = ws.get_all_values()
            # Asumimos que los encabezados están en la fila 5 (índice 4)
            if len(raw_data) > 5:
                headers = raw_data[4]
                rows = raw_data[5:]
                temp_df = pd.DataFrame(rows, columns=headers)
                temp_df['Consultor'] = consultor
                
                # Limpiar columnas de tiempo
                for c_tiempo in ['Tiempo estimado', 'Tiempo real']:
                    if c_tiempo in temp_df.columns:
                        # Reemplazar coma por punto para decimales de horas
                        temp_df[c_tiempo] = temp_df[c_tiempo].astype(str).str.replace(',', '.', regex=False)
                        temp_df[c_tiempo] = pd.to_numeric(temp_df[c_tiempo], errors='coerce').fillna(0)
                
                all_tasks.append(temp_df)
        except Exception:
            pass # Si una hoja no existe, continuamos
            
    df_ops = pd.concat(all_tasks, ignore_index=True) if all_tasks else pd.DataFrame()

    return df_fin, df_ops, col_monto

# --- CONFIGURACIÓN DE IDs (TU PARTE) ---
# 👇 PEGA AQUÍ TUS IDs REALES 👇
ID_FINANCIERO = "1ldntONNpWFgXPcF8VINDKzNAhG_vGMdzGEOESM3aLNU"
ID_BACKLOG    = "1jpj48uvz-AE0yg5gA-RO0oQb59tFv9Zt"
# 👆 -------------------------- 👆

# Carga de Datos
try:
    df_fin, df_ops, col_monto = load_data(ID_FINANCIERO, ID_BACKLOG)
except Exception as e:
    st.error(f"Error cargando datos: {e}")
    st.stop()

# --- INTERFAZ DE USUARIO ---
st.sidebar.title("goBIG Intelligence")
st.sidebar.markdown("---")
view_mode = st.sidebar.radio("Navegación:", 
    ["1. Financiera (Cash Flow)", 
     "2. Rentabilidad (Clientes)", 
     "3. Operativa (Eficiencia)"])

st.sidebar.info("🟢 Sistema Online")

# --- VISTA 1: FINANCIERA ---
if "Financiera" in view_mode:
    st.title("💰 Financiera: Flujo de Caja Real")
    
    if col_monto and not df_fin.empty:
        # KPIs
        ingresos = df_fin[df_fin[col_monto] > 0][col_monto].sum()
        egresos = df_fin[df_fin[col_monto] < 0][col_monto].sum()
        balance = ingresos + egresos
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Ingresos Totales", f"${ingresos:,.0f}")
        c2.metric("Egresos Totales", f"${egresos:,.0f}")
        c3.metric("Flujo de Caja Neto", f"${balance:,.0f}", delta_color="normal")
        
        st.markdown("---")
        
        # Gráfica Principal: Balance por Centro de Costos
        # Buscamos la columna de Centro de Costos flexiblemente
        col_cc = next((c for c in df_fin.columns if "Centro" in c), None)
        
        if col_cc:
            df_grouped = df_fin.groupby(col_cc)[col_monto].sum().reset_index()
            # Ordenamos para ver mejor los ganadores y perdedores
            df_grouped = df_grouped.sort_values(by=col_monto, ascending=False)
            
            fig = px.bar(df_grouped, x=col_cc, y=col_monto, 
                         color=col_monto, 
                         color_continuous_scale="RdBu",
                         title="Balance por Cliente / Centro de Costos",
                         text_auto='.2s')
            fig.update_layout(template="plotly_dark", height=500)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning("No se detectó columna de Centro de Costos.")
    else:
        st.info("No hay datos financieros registrados aún.")

# --- VISTA 2: RENTABILIDAD ---
elif "Rentabilidad" in view_mode:
    st.title("💎 Rentabilidad por Cliente")
    st.markdown("""
    > **Objetivo:** Cruzar lo facturado vs. lo que nos cuesta el equipo.
    """)
    st.info("🚧 Próximo paso: Conectar Hoja de Facturación y Diccionario de Recursos.")
    
    # Mostramos un adelanto de la actividad del equipo
    if not df_ops.empty:
        st.subheader("Esfuerzo del Equipo (Input de Costos)")
        df_costos = df_ops.groupby("Nombre del cliente")['Tiempo real'].sum().reset_index()
        fig = px.pie(df_costos, values='Tiempo real', names='Nombre del cliente', hole=0.4, title="Distribución de Horas por Cliente")
        fig.update_layout(template="plotly_dark")
        st.plotly_chart(fig)

# --- VISTA 3: OPERATIVA ---
elif "Operativa" in view_mode:
    st.title("⚙️ Operativa: Desempeño del Equipo")
    
    if not df_ops.empty:
        # KPIs Generales
        total_horas = df_ops['Tiempo real'].sum()
        total_estimado = df_ops['Tiempo estimado'].sum()
        
        k1, k2 = st.columns(2)
        k1.metric("Horas Ejecutadas (Real)", f"{total_horas:.1f} h")
        k2.metric("Horas Planificadas", f"{total_estimado:.1f} h")
        
        st.markdown("---")
        
        # Gráfica 1: Eficiencia por Consultor
        st.subheader("1. Precisión de Estimaciones")
        df_eff = df_ops.groupby("Consultor")[['Tiempo estimado', 'Tiempo real']].sum().reset_index()
        
        fig_eff = go.Figure()
        fig_eff.add_trace(go.Bar(x=df_eff['Consultor'], y=df_eff['Tiempo estimado'], name='Estimado', marker_color='#4a86e8'))
        fig_eff.add_trace(go.Bar(x=df_eff['Consultor'], y=df_eff['Tiempo real'], name='Real', marker_color='#fbbc04'))
        fig_eff.update_layout(barmode='group', template="plotly_dark", title="¿Quién está sobre o sub estimando?")
        st.plotly_chart(fig_eff, use_container_width=True)
        
        # Gráfica 2: Carga de Trabajo
        st.subheader("2. Tipos de Tarea")
        if 'Tipo de tarea' in df_ops.columns:
            fig_tree = px.treemap(df_ops, path=['Tipo de tarea', 'Consultor'], values='Tiempo real', 
                                  title="Mapa de Calor de Actividades")
            fig_tree.update_layout(template="plotly_dark")
            st.plotly_chart(fig_tree, use_container_width=True)
            
    else:
        st.warning("⚠️ No se encontraron datos en el Backlog. Verifica que los nombres de las pestañas en el Sheet coincidan con los nombres en el código: Sebastian Saenz, Alejandra Buriticá, etc.")
