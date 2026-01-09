import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import gspread
from google.oauth2.service_account import Credentials
import json
from datetime import datetime, date, timedelta

# --- 1. CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="goBIG BI 2026", page_icon="🚀", layout="wide")
st.markdown("""<style>.main {background-color: #0e1117;} .stMetric {background-color: #262730; border: 1px solid #444;}</style>""", unsafe_allow_html=True)

# --- 2. UTILIDADES Y MAPEOS ---

# MAPEO CLAVE: Conecta el nombre de la Pestaña (Backlog) con el nombre del Costo (Diccionario)
# Esto soluciona el error de que desaparezcan colaboradores.
MAPA_CONSULTORES = {
    "Jimmy Peña": "JIMMY PEÑA",
    "Alejandra Buriticá": "ALEJANDRA BURITICA",
    "Alejandra Cárdenas": "MARIA ALEJANDRA CARDENAS",
    "Sebastian Saenz": "SEBASTIAN SAENZ"
}

def limpiar_moneda_colombia(serie):
    """Convierte strings de moneda ($ 1.000,00) a números."""
    serie = serie.astype(str).str.replace(r'[$\s]', '', regex=True).str.replace('.', '', regex=False).str.replace(',', '.', regex=False)
    return pd.to_numeric(serie, errors='coerce').fillna(0)

def get_colombia_holidays_2026():
    return ["2026-01-01", "2026-01-12", "2026-03-23", "2026-03-26", "2026-03-27", "2026-05-01", 
            "2026-05-18", "2026-06-08", "2026-06-15", "2026-06-29", "2026-07-20", "2026-08-07", 
            "2026-08-17", "2026-10-12", "2026-11-02", "2026-11-16", "2026-12-08", "2026-12-25"]

# --- 3. CARGA DE DATOS ROBUSTA ---
@st.cache_data(ttl=600)
def load_data(ids):
    json_str = st.secrets["credenciales_json"]
    key_dict = json.loads(json_str, strict=False)
    creds = Credentials.from_service_account_info(key_dict, scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"])
    client = gspread.authorize(creds)
    
    # 0. ABRIR LIBROS
    sh_fin = client.open_by_key(ids['fin'])
    sh_ops = client.open_by_key(ids['ops']) 

    # --- A. CARGAR COSTOS (DICCIONARIO) ---
    try:
        df_costos = pd.DataFrame(sh_fin.worksheet("04_Diccionario de recursos desde 2026").get_all_records())
        # Limpieza Costo Hora
        col_costo = next((c for c in df_costos.columns if "Costo Hora" in c), None)
        if col_costo: df_costos[col_costo] = limpiar_moneda_colombia(df_costos[col_costo])
        # Estandarizar nombre en Diccionario (Todo Mayúsculas)
        df_costos['COLABORADOR'] = df_costos['COLABORADOR'].astype(str).str.strip().str.upper()
    except:
        df_costos = pd.DataFrame()

    # --- B. CARGAR BACKLOG (OPERATIVA) ---
    all_tasks = []
    
    # Iteramos por la lista FIJA de pestañas que sabemos que existen
    lista_pestanas_reales = list(MAPA_CONSULTORES.keys()) 

    for nombre_pestana in lista_pestanas_reales:
        try:
            raw = sh_ops.worksheet(nombre_pestana).get_all_values()
            
            # El encabezado azul está en la Fila 5 (índice 4)
            if len(raw) > 5:
                header = raw[4]
                data = raw[5:]
                df = pd.DataFrame(data, columns=header)
                
                # Asignamos el nombre de la pestaña (ej. "Alejandra Cárdenas")
                df['Consultor_Pestana'] = nombre_pestana 
                
                # Asignamos el nombre NORMALIZADO para cruce de costos (ej. "MARIA ALEJANDRA CARDENAS")
                df['Consultor_Cruce'] = MAPA_CONSULTORES.get(nombre_pestana, nombre_pestana.upper())

                # Limpieza de números
                for c in ['Tiempo estimado', 'Tiempo real']:
                    if c in df.columns:
                        df[c] = pd.to_numeric(df[c].astype(str).str.replace(',', '.'), errors='coerce').fillna(0)
                
                # Limpieza de fechas
                if 'Fecha de entrega' in df.columns:
                    df['Fecha de entrega'] = pd.to_datetime(df['Fecha de entrega'], dayfirst=True, errors='coerce')

                all_tasks.append(df)
        except Exception as e:
            # Si falla una pestaña específica, no rompemos todo, solo avisamos en consola
            print(f"Error leyendo pestaña {nombre_pestana}: {e}")
            continue

    df_ops = pd.concat(all_tasks, ignore_index=True) if all_tasks else pd.DataFrame()

    # --- C. CARGAR FINANCIERA Y PROYECCIONES ---
    # Movimientos Financieros
    df_fin = pd.DataFrame(sh_fin.worksheet("01_Movimientos financieros desde 2026").get_all_records())
    df_fin.columns = df_fin.columns.str.strip()
    col_monto = next((c for c in df_fin.columns if "Monto" in c or "Valor" in c), None)
    col_fecha = next((c for c in df_fin.columns if "Fecha" in c), None)
    if col_monto: df_fin[col_monto] = limpiar_moneda_colombia(df_fin[col_monto])

    # Costos Fijos
    try:
        df_fijos = pd.DataFrame(sh_fin.worksheet("05_Costos fijos desde 2026").get_all_records())
        col_fijo = next((c for c in df_fijos.columns if "Monto" in c), None)
        total_fijos = limpiar_moneda_colombia(df_fijos[col_fijo]).sum() if col_fijo else 0
    except: total_fijos = 0
    
    # Facturación
    try:
        df_fact = pd.DataFrame(sh_fin.worksheet("02_Cuadro de facturación desde 2026").get_all_records())
        col_fact_total = next((c for c in df_fact.columns if "Total" in c or "Precio" in c), None)
        col_fact_mes = next((c for c in df_fact.columns if "Mes" in c), None)
        if col_fact_total: df_fact[col_fact_total] = limpiar_moneda_colombia(df_fact[col_fact_total])
    except:
        df_fact = pd.DataFrame()
        col_fact_total, col_fact_mes = None, None

    return df_fin, df_ops, df_fact, df_costos, total_fijos, col_monto, col_fecha, col_fact_total, col_fact_mes

# --- 4. EJECUCIÓN ---
IDS = {
    'fin': "1ldntONNpWFgXPcF8VINDKzNAhG_vGMdzGEOESM3aLNU",
    'ops': "1Vl5rhQDi6YooJgjYAF76oOO0aN8rbPtu07giky36wSo",
    'fact': "1ldntONNpWFgXPcF8VINDKzNAhG_vGMdzGEOESM3aLNU", 
    'fijos': "1ldntONNpWFgXPcF8VINDKzNAhG_vGMdzGEOESM3aLNU"
}

try:
    df_fin, df_ops, df_fact, df_costos, total_fijos, col_monto, col_fecha, col_fact, col_mes = load_data(IDS)
except Exception as e:
    st.error(f"Error crítico cargando datos: {e}")
    st.stop()

# --- 5. INTERFAZ Y NAVEGACIÓN ---
st.sidebar.title("goBIG Intelligence")
page = st.sidebar.radio("Navegación:", 
    ["🏠 Home", "💰 Financiera", "💎 Rentabilidad", "⚙️ Operativa", "📈 Comercial"])

# ==========================
# PÁGINA: HOME
# ==========================
if "Home" in page:
    st.title("🏠 Tablero de Control 2026")
    hoy = datetime.now()
    inicio = datetime(2026, 1, 1)
    dias = (hoy - inicio).days + 1
    progreso = dias / 365
    
    # Días hábiles
    festivos = get_colombia_holidays_2026()
    habiles = 0
    temp = inicio
    while temp <= hoy:
        if temp.weekday() < 5 and str(temp.date()) not in festivos: habiles += 1
        temp += timedelta(days=1)
        
    c1, c2, c3 = st.columns(3)
    c1.metric("Progreso Año", f"{progreso*100:.1f}%", f"Día {dias}")
    c2.metric("Días Hábiles", f"{habiles}", "Acumulados")
    c3.metric("Costos Fijos Base", f"${total_fijos:,.0f}", "Mensual")

# ==========================
# PÁGINA: FINANCIERA
# ==========================
elif "Financiera" in page:
    st.title("💰 Financiera: Plan vs. Realidad")
    
    meses_orden = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
    data_chart = []
    
    # 1. Proyectado
    for mes in meses_orden:
        val_fact = 0
        if not df_fact.empty and col_mes:
            val_fact = df_fact[df_fact[col_mes].astype(str).str.lower() == mes][col_fact].sum()
        
        data_chart.append({"Mes": mes, "Tipo": "Proyectado Ingreso", "Monto": val_fact})
        data_chart.append({"Mes": mes, "Tipo": "Proyectado Egreso", "Monto": total_fijos})

    # 2. Real
    if not df_fin.empty and col_fecha:
        mapa_meses = {1: 'enero', 2: 'febrero', 3: 'marzo', 4: 'abril', 5: 'mayo', 6: 'junio', 
                      7: 'julio', 8: 'agosto', 9: 'septiembre', 10: 'octubre', 11: 'noviembre', 12: 'diciembre'}
        
        df_fin['Dt'] = pd.to_datetime(df_fin[col_fecha], dayfirst=True, errors='coerce')
        df_fin['Mes_Str'] = df_fin['Dt'].dt.month.map(mapa_meses)
        
        for mes in meses_orden:
            df_m = df_fin[df_fin['Mes_Str'] == mes]
            ing = df_m[df_m[col_monto] > 0][col_monto].sum() if not df_m.empty else 0
            egr = abs(df_m[df_m[col_monto] < 0][col_monto].sum()) if not df_m.empty else 0
            
            data_chart.append({"Mes": mes, "Tipo": "Real Ingreso", "Monto": ing})
            data_chart.append({"Mes": mes, "Tipo": "Real Egreso", "Monto": egr})
            
    df_viz = pd.DataFrame(data_chart)
    
    fig = go.Figure()
    # Líneas Meta
    fig.add_trace(go.Scatter(x=df_viz[df_viz['Tipo']=="Proyectado Ingreso"]['Mes'], y=df_viz[df_viz['Tipo']=="Proyectado Ingreso"]['Monto'], name="Meta Ingreso", line=dict(dash='dot', color='#00CC96')))
    fig.add_trace(go.Scatter(x=df_viz[df_viz['Tipo']=="Proyectado Egreso"]['Mes'], y=df_viz[df_viz['Tipo']=="Proyectado Egreso"]['Monto'], name="Presupuesto Fijo", line=dict(dash='dot', color='#EF553B')))
    # Barras Reales
    fig.add_trace(go.Bar(x=df_viz[df_viz['Tipo']=="Real Ingreso"]['Mes'], y=df_viz[df_viz['Tipo']=="Real Ingreso"]['Monto'], name="Ingreso Real", marker_color='#00CC96', opacity=0.7))
    fig.add_trace(go.Bar(x=df_viz[df_viz['Tipo']=="Real Egreso"]['Mes'], y=df_viz[df_viz['Tipo']=="Real Egreso"]['Monto'], name="Egreso Real", marker_color='#EF553B', opacity=0.7))
    
    fig.update_layout(template="plotly_dark", barmode='group', height=500)
    st.plotly_chart(fig, use_container_width=True)

# ==========================
# PÁGINA: RENTABILIDAD
# ==========================
elif "Rentabilidad" in page:
    st.title("💎 Rentabilidad Operativa (Burn Rate)")
    st.markdown("Costo calculado: **Horas Reales (Backlog) x Costo Hora (Nómina)**.")

    if df_ops.empty:
        st.error("No se pudieron cargar datos operativos.")
    else:
        # Cruce Maestro usando 'Consultor_Cruce' (normalizado) y 'COLABORADOR'
        df_rent = pd.merge(df_ops, df_costos, left_on='Consultor_Cruce', right_on='COLABORADOR', how='left')
        
        # Cálculo
        col_costo_h = next((c for c in df_rent.columns if "Costo Hora" in c), None)
        if col_costo_h:
            df_rent['Costo_Devengado'] = df_rent['Tiempo real'] * df_rent[col_costo_h]
            df_rent['Costo_Devengado'] = df_rent['Costo_Devengado'].fillna(0)
            
            # KPIs
            k1, k2, k3 = st.columns(3)
            k1.metric("Total Horas Reportadas", f"{df_rent['Tiempo real'].sum():.1f} h")
            k2.metric("Costo Nómina Consumido", f"${df_rent['Costo_Devengado'].sum():,.0f}")
            k3.metric("Tickets Procesados", len(df_rent))
            
            st.divider()
            
            # Gráficas
            c_izq, c_der = st.columns(2)
            with c_izq:
                st.subheader("📆 Evolución de Costo Diario")
                if 'Fecha de entrega' in df_rent.columns:
                    # Filtramos solo 2026 y fechas validas
                    df_linea = df_rent.dropna(subset=['Fecha de entrega'])
                    df_linea = df_linea[df_linea['Fecha de entrega'].dt.year == 2026]
                    
                    df_diario = df_linea.groupby('Fecha de entrega')['Costo_Devengado'].sum().reset_index()
                    fig_burn = px.bar(df_diario, x='Fecha de entrega', y='Costo_Devengado', color_discrete_sequence=['#FF4B4B'])
                    st.plotly_chart(fig_burn, use_container_width=True)
            
            with c_der:
                st.subheader("👥 Costo por Cliente")
                if 'Nombre del cliente' in df_rent.columns:
                    df_cli = df_rent.groupby('Nombre del cliente')['Costo_Devengado'].sum().reset_index().sort_values('Costo_Devengado', ascending=True)
                    fig_cli = px.bar(df_cli, x='Costo_Devengado', y='Nombre del cliente', orientation='h')
                    st.plotly_chart(fig_cli, use_container_width=True)
        else:
            st.warning("No se encontró columna de Costo Hora. Verifica nombres en Diccionario.")

# ==========================
# PÁGINA: OPERATIVA
# ==========================
elif "Operativa" in page:
    st.title("⚙️ Operativa: Distribución de Esfuerzo")
    
    if not df_ops.empty:
        # Treemap Global
        st.subheader("Mapa de Calor: ¿En qué se van las horas?")
        if 'Consultor_Pestana' in df_ops.columns and 'Tipo de tarea' in df_ops.columns:
            # Agrupamos para limpiar visualización
            df_tree = df_ops.groupby(['Consultor_Pestana', 'Tipo de tarea'])['Tiempo real'].sum().reset_index()
            # Filtramos ceros
            df_tree = df_tree[df_tree['Tiempo real'] > 0]
            
            fig = px.treemap(df_tree, path=['Consultor_Pestana', 'Tipo de tarea'], values='Tiempo real', color='Consultor_Pestana')
            fig.update_layout(template="plotly_dark", height=600)
            st.plotly_chart(fig, use_container_width=True)
            
        # Tabla Detallada
        with st.expander("Ver Detalle de Tareas"):
            st.dataframe(df_ops[['Fecha de entrega', 'Consultor_Pestana', 'Nombre del cliente', 'Tipo de tarea', 'Tiempo real']])
    else:
        st.error("No hay datos cargados. Verifica los nombres de las pestañas en el código.")

# ==========================
# PÁGINA: COMERCIAL
# ==========================
elif "Comercial" in page:
    st.title("📈 Comercial & Proyección")
    st.info("🚧 FASE 5: Próximamente Funnel de Ventas y Runway.")
