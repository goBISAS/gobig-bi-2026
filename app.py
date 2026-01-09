import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import gspread
from google.oauth2.service_account import Credentials
import json
from datetime import datetime, date

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="goBIG BI 2026", page_icon="🚀", layout="wide")
st.markdown("""<style>.main {background-color: #0e1117;} .stMetric {background-color: #262730; border: 1px solid #444;}</style>""", unsafe_allow_html=True)

# --- UTILIDADES ---
def limpiar_moneda_colombia(serie):
    serie = serie.astype(str).str.replace(r'[$\s]', '', regex=True).str.replace('.', '', regex=False).str.replace(',', '.', regex=False)
    return pd.to_numeric(serie, errors='coerce').fillna(0)

def get_colombia_holidays_2026():
    # Festivos 2026
    return ["2026-01-01", "2026-01-12", "2026-03-23", "2026-03-26", "2026-03-27", "2026-05-01", 
            "2026-05-18", "2026-06-08", "2026-06-15", "2026-06-29", "2026-07-20", "2026-08-07", 
            "2026-08-17", "2026-10-12", "2026-11-02", "2026-11-16", "2026-12-08", "2026-12-25"]

# --- CARGA DE DATOS ---
@st.cache_data(ttl=600)
def load_data(ids):
    json_str = st.secrets["credenciales_json"]
    key_dict = json.loads(json_str, strict=False)
    creds = Credentials.from_service_account_info(key_dict, scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"])
    client = gspread.authorize(creds)
    
    # 1. FINANCIERO (REAL)
    df_fin = pd.DataFrame(client.open_by_key(ids['fin']).worksheet("01_Movimientos financieros desde 2026").get_all_records())
    df_fin.columns = df_fin.columns.str.strip()
    col_monto = next((c for c in df_fin.columns if "Monto" in c or "Valor" in c), None)
    col_fecha = next((c for c in df_fin.columns if "Fecha" in c), None)
    if col_monto: df_fin[col_monto] = limpiar_moneda_colombia(df_fin[col_monto])
    
    # 2. BACKLOG (OPERATIVA)
    sh_ops = client.open_by_key(ids['ops'])
    all_tasks = []
    for consultor in ["Sebastian Saenz", "Alejandra Buriticá", "Alejandra Cárdenas", "Jimmy Peña"]:
        try:
            raw = sh_ops.worksheet(consultor).get_all_values()
            if len(raw) > 5:
                df = pd.DataFrame(raw[5:], columns=raw[4])
                df['Consultor'] = consultor
                for c in ['Tiempo estimado', 'Tiempo real']:
                    if c in df.columns:
                        df[c] = pd.to_numeric(df[c].astype(str).str.replace(',', '.'), errors='coerce').fillna(0)
                all_tasks.append(df)
        except: pass
    df_ops = pd.concat(all_tasks, ignore_index=True) if all_tasks else pd.DataFrame()

    # 3. PROYECCIÓN (FACTURACIÓN Y COSTOS FIJOS) - NUEVO FASE 2
    # Costos Fijos
    try:
        df_fijos = pd.DataFrame(client.open_by_key(ids['fijos']).worksheet("05_Costos fijos desde 2026").get_all_records())
        col_monto_fijo = next((c for c in df_fijos.columns if "Monto" in c), None)
        total_fijos_mes = limpiar_moneda_colombia(df_fijos[col_monto_fijo]).sum() if col_monto_fijo else 0
    except: total_fijos_mes = 0
    
    # Facturación Proyectada
    try:
        df_fact = pd.DataFrame(client.open_by_key(ids['fact']).worksheet("02_Cuadro de facturación desde 2026").get_all_records())
        col_total_fact = next((c for c in df_fact.columns if "Total" in c or "Precio" in c), None) # Buscamos Total Factura
        col_mes_fact = next((c for c in df_fact.columns if "Mes" in c), None)
        if col_total_fact: df_fact[col_total_fact] = limpiar_moneda_colombia(df_fact[col_total_fact])
    except: 
        df_fact = pd.DataFrame()
        col_total_fact, col_mes_fact = None, None

    return df_fin, df_ops, df_fact, total_fijos_mes, col_monto, col_fecha, col_total_fact, col_mes_fact

# --- IDs ---
IDS = {
    'fin': "1ldntONNpWFgXPcF8VINDKzNAhG_vGMdzGEOESM3aLNU", # Financiero
    'ops': "1Vl5rhQDi6YooJgjYAF76oOO0aN8rbPtu07giky36wSo", # Backlog
    'fact': "1ldntONNpWFgXPcF8VINDKzNAhG_vGMdzGEOESM3aLNU", # Facturación (Asumiendo que está en el mismo archivo maestro)
    'fijos': "1ldntONNpWFgXPcF8VINDKzNAhG_vGMdzGEOESM3aLNU" # Costos Fijos (Asumiendo que está en el mismo archivo maestro)
}
# NOTA: He puesto el mismo ID para facturación y fijos porque en tu PDF decían "Link al archivo maestro". 
# Si están en otro archivo, cámbialos.

try:
    df_fin, df_ops, df_fact, total_fijos, col_monto, col_fecha, col_fact, col_mes = load_data(IDS)
except Exception as e:
    st.error(f"Error cargando datos: {e}")
    st.stop()

# --- INTERFAZ ---
st.sidebar.title("goBIG Intelligence")
page = st.sidebar.radio("Navegación:", ["🏠 Home", "💰 Financiera", "⚙️ Operativa"])

if "Home" in page:
    st.title("🏠 Tablero de Control 2026")
    
    # Lógica de Fechas (Desde Enero 1)
    hoy = datetime.now()
    inicio = datetime(2026, 1, 1)
    fin = datetime(2026, 12, 31)
    
    dias_transcurridos = (hoy - inicio).days + 1
    progreso = dias_transcurridos / 365
    
    # Días Hábiles
    from datetime import timedelta
    festivos = get_colombia_holidays_2026()
    habiles_pasados = 0
    temp = inicio
    while temp <= hoy:
        if temp.weekday() < 5 and str(temp.date()) not in festivos: habiles_pasados += 1
        temp += timedelta(days=1)
        
    c1, c2, c3 = st.columns(3)
    c1.metric("Progreso Año 2026", f"{progreso*100:.1f}%", f"Día {dias_transcurridos}")
    c2.metric("Días Hábiles Pasados", f"{habiles_pasados} días", "Desde Ene 1")
    c3.metric("Costos Fijos Mensuales", f"${total_fijos:,.0f}", "Base Operativa")

elif "Financiera" in page:
    st.title("💰 Financiera: Plan vs. Realidad")
    
    # 1. Preparar Datos para Gráfica
    meses_orden = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
    
    # A) Proyectado (Presupuesto)
    datos_proyeccion = []
    for mes in meses_orden:
        # Ingresos Proyectados (Suma facturas de ese mes)
        ingreso_mes = 0
        if not df_fact.empty and col_mes and col_fact:
            ingreso_mes = df_fact[df_fact[col_mes].str.lower() == mes][col_fact].sum()
        
        datos_proyeccion.append({
            "Mes": mes, 
            "Tipo": "Proyectado Ingreso", 
            "Monto": ingreso_mes
        })
        datos_proyeccion.append({
            "Mes": mes, 
            "Tipo": "Proyectado Egreso (Fijo)", 
            "Monto": total_fijos # Asumimos fijo constante
        })
        
    # B) Real (Ejecutado)
    # Necesitamos extraer el mes de la fecha del movimiento financiero
    if not df_fin.empty and col_fecha:
        # Convertir fecha a datetime y sacar nombre mes
        # Formatos posibles: DD/MM/YYYY o YYYY-MM-DD
        df_fin['Fecha_dt'] = pd.to_datetime(df_fin[col_fecha], dayfirst=True, errors='coerce')
        df_fin['Mes_Nombre'] = df_fin['Fecha_dt'].dt.month_name(locale='es_ES') # Requiere locale, hacemos mapa manual mejor
        mapa_meses = {1: 'enero', 2: 'febrero', 3: 'marzo', 4: 'abril', 5: 'mayo', 6: 'junio', 
                      7: 'julio', 8: 'agosto', 9: 'septiembre', 10: 'octubre', 11: 'noviembre', 12: 'diciembre'}
        df_fin['Mes_Nombre'] = df_fin['Fecha_dt'].dt.month.map(mapa_meses)
        
        for mes in meses_orden:
            df_mes = df_fin[df_fin['Mes_Nombre'] == mes]
            ingreso_real = df_mes[df_mes[col_monto] > 0][col_monto].sum()
            egreso_real = abs(df_mes[df_mes[col_monto] < 0][col_monto].sum()) # Valor absoluto para comparar
            
            datos_proyeccion.append({"Mes": mes, "Tipo": "Real Ingreso", "Monto": ingreso_real})
            datos_proyeccion.append({"Mes": mes, "Tipo": "Real Egreso", "Monto": egreso_real})

    df_chart = pd.DataFrame(datos_proyeccion)
    
    # 2. Gráfica Combinada
    st.subheader("Evolución Mensual: Lo que dijimos vs. Lo que hicimos")
    
    fig = go.Figure()
    
    # Líneas de Proyección
    df_p_in = df_chart[df_chart['Tipo'] == "Proyectado Ingreso"]
    fig.add_trace(go.Scatter(x=df_p_in['Mes'], y=df_p_in['Monto'], name="Proy. Facturación", line=dict(color='#00CC96', dash='dot')))
    
    df_p_out = df_chart[df_chart['Tipo'] == "Proyectado Egreso (Fijo)"]
    fig.add_trace(go.Scatter(x=df_p_out['Mes'], y=df_p_out['Monto'], name="Proy. Costos Fijos", line=dict(color='#EF553B', dash='dot')))
    
    # Barras Reales
    df_r_in = df_chart[df_chart['Tipo'] == "Real Ingreso"]
    fig.add_trace(go.Bar(x=df_r_in['Mes'], y=df_r_in['Monto'], name="Ingreso Real", marker_color='#00CC96', opacity=0.6))
    
    df_r_out = df_chart[df_chart['Tipo'] == "Real Egreso"]
    fig.add_trace(go.Bar(x=df_r_out['Mes'], y=df_r_out['Monto'], name="Egreso Real", marker_color='#EF553B', opacity=0.6))
    
    fig.update_layout(template="plotly_dark", barmode='group', height=500)
    st.plotly_chart(fig, use_container_width=True)

elif "Operativa" in page:
    st.title("⚙️ Operativa")
    # Treemap por Colaborador
    if not df_ops.empty:
        st.subheader("Mapa de Calor de Esfuerzo")
        # Aseguramos que existan las columnas
        if 'Consultor' in df_ops.columns and 'Tipo de tarea' in df_ops.columns:
            fig = px.treemap(df_ops, path=['Consultor', 'Tipo de tarea'], values='Tiempo real', color='Consultor')
            fig.update_layout(template="plotly_dark")
            st.plotly_chart(fig, use_container_width=True)
