import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import gspread
from google.oauth2.service_account import Credentials
import json
from datetime import datetime, date, timedelta

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="goBIG BI 2026", page_icon="🚀", layout="wide")
st.markdown("""<style>.main {background-color: #0e1117;} .stMetric {background-color: #262730; border: 1px solid #444;}</style>""", unsafe_allow_html=True)

# --- UTILIDADES ---
def limpiar_moneda_colombia(serie):
    """Limpia formatos de moneda ($ 1.000,00) a números flotantes."""
    serie = serie.astype(str).str.replace(r'[$\s]', '', regex=True).str.replace('.', '', regex=False).str.replace(',', '.', regex=False)
    return pd.to_numeric(serie, errors='coerce').fillna(0)

def get_colombia_holidays_2026():
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
    
    # 0. ABRIR HOJAS MAESTRAS
    sh_fin = client.open_by_key(ids['fin'])
    sh_ops = client.open_by_key(ids['ops']) # Backlog

    # 1. DICCIONARIO DE COSTOS (NUEVO: Para Rentabilidad)
    #
    try:
        df_costos = pd.DataFrame(sh_fin.worksheet("04_Diccionario de recursos desde 2026").get_all_records())
        # Limpieza de costo hora
        col_costo_hora = next((c for c in df_costos.columns if "Costo Hora" in c), None)
        if col_costo_hora:
            df_costos[col_costo_hora] = limpiar_moneda_colombia(df_costos[col_costo_hora])
        # Normalizar nombres para cruce
        df_costos['COLABORADOR'] = df_costos['COLABORADOR'].astype(str).str.strip().str.upper()
    except Exception as e:
        df_costos = pd.DataFrame()
        
    # 2. FINANCIERO (REAL)
    df_fin = pd.DataFrame(sh_fin.worksheet("01_Movimientos financieros desde 2026").get_all_records())
    df_fin.columns = df_fin.columns.str.strip()
    col_monto = next((c for c in df_fin.columns if "Monto" in c or "Valor" in c), None)
    col_fecha = next((c for c in df_fin.columns if "Fecha" in c), None)
    if col_monto: df_fin[col_monto] = limpiar_moneda_colombia(df_fin[col_monto])
    
    # 3. BACKLOG (OPERATIVA + RENTABILIDAD)
    #
    all_tasks = []
    
    # Obtenemos lista de consultores desde el diccionario para ser dinámicos, 
    # si falla, usamos lista default.
    if not df_costos.empty:
        lista_consultores = df_costos['COLABORADOR'].unique().tolist()
    else:
        lista_consultores = ["SEBASTIAN SAENZ", "ALEJANDRA BURITICÁ", "ALEJANDRA CÁRDENAS", "JIMMY PEÑA"]

    for consultor_upper in lista_consultores:
        try:
            # Intentamos convertir nombre UPPER a Title Case (ej. JIMMY PEÑA -> Jimmy Peña) para hallar la pestaña
            nombre_pestana = consultor_upper.title()
            
            # Obtener todos los valores de la hoja
            raw = sh_ops.worksheet(nombre_pestana).get_all_values()
            
            # LÓGICA DE ENCABEZADO: Fila 5 (índice 4) es el azul. Datos inician en Fila 6.
            if len(raw) > 5:
                header = raw[4] # Fila 5
                data = raw[5:]  # Fila 6 en adelante
                
                df = pd.DataFrame(data, columns=header)
                df['Consultor'] = consultor_upper # Guardamos en Mayúscula para cruzar fácil
                
                # Limpieza de números
                for c in ['Tiempo estimado', 'Tiempo real']:
                    if c in df.columns:
                        df[c] = pd.to_numeric(df[c].astype(str).str.replace(',', '.'), errors='coerce').fillna(0)
                
                # Limpieza de fechas
                if 'Fecha de entrega' in df.columns:
                    df['Fecha de entrega'] = pd.to_datetime(df['Fecha de entrega'], dayfirst=True, errors='coerce')
                    
                all_tasks.append(df)
        except: 
            continue # Si no existe la pestaña, saltamos
            
    df_ops = pd.concat(all_tasks, ignore_index=True) if all_tasks else pd.DataFrame()

    # 4. PROYECCIÓN (FACTURACIÓN Y COSTOS FIJOS)
    try:
        df_fijos = pd.DataFrame(sh_fin.worksheet("05_Costos fijos desde 2026").get_all_records())
        col_monto_fijo = next((c for c in df_fijos.columns if "Monto" in c), None)
        total_fijos_mes = limpiar_moneda_colombia(df_fijos[col_monto_fijo]).sum() if col_monto_fijo else 0
    except: total_fijos_mes = 0
    
    try:
        df_fact = pd.DataFrame(sh_fin.worksheet("02_Cuadro de facturación desde 2026").get_all_records())
        col_total_fact = next((c for c in df_fact.columns if "Total" in c or "Precio" in c), None)
        col_mes_fact = next((c for c in df_fact.columns if "Mes" in c), None)
        if col_total_fact: df_fact[col_total_fact] = limpiar_moneda_colombia(df_fact[col_total_fact])
    except: 
        df_fact = pd.DataFrame()
        col_total_fact, col_mes_fact = None, None

    return df_fin, df_ops, df_fact, df_costos, total_fijos_mes, col_monto, col_fecha, col_total_fact, col_mes_fact

# --- IDs (Configura aquí tus IDs correctos) ---
IDS = {
    'fin': "1ldntONNpWFgXPcF8VINDKzNAhG_vGMdzGEOESM3aLNU", # BI Financiero
    'ops': "1Vl5rhQDi6YooJgjYAF76oOO0aN8rbPtu07giky36wSo", # Backlog 2026
    'fact': "1ldntONNpWFgXPcF8VINDKzNAhG_vGMdzGEOESM3aLNU", 
    'fijos': "1ldntONNpWFgXPcF8VINDKzNAhG_vGMdzGEOESM3aLNU"
}

try:
    df_fin, df_ops, df_fact, df_costos, total_fijos, col_monto, col_fecha, col_fact, col_mes = load_data(IDS)
except Exception as e:
    st.error(f"Error cargando datos. Verifica los IDs y nombres de hojas: {e}")
    st.stop()

# --- INTERFAZ ---
st.sidebar.title("goBIG Intelligence")
page = st.sidebar.radio("Navegación:", 
    ["🏠 Home", 
     "💰 Financiera", 
     "💎 Rentabilidad", 
     "⚙️ Operativa", 
     "📈 Comercial"])

# --- 1. HOME ---
if "Home" in page:
    st.title("🏠 Tablero de Control 2026")
    hoy = datetime.now()
    inicio = datetime(2026, 1, 1)
    dias_transcurridos = (hoy - inicio).days + 1
    progreso = dias_transcurridos / 365
    
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

# --- 2. FINANCIERA ---
elif "Financiera" in page:
    st.title("💰 Financiera: Plan vs. Realidad")
    
    meses_orden = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
    datos_proyeccion = []
    
    # Proyectado
    for mes in meses_orden:
        ingreso_mes = 0
        if not df_fact.empty and col_mes and col_fact:
            ingreso_mes = df_fact[df_fact[col_mes].astype(str).str.lower() == mes][col_fact].sum()
        
        datos_proyeccion.append({"Mes": mes, "Tipo": "Proyectado Ingreso", "Monto": ingreso_mes})
        datos_proyeccion.append({"Mes": mes, "Tipo": "Proyectado Egreso (Fijo)", "Monto": total_fijos})
        
    # Real
    if not df_fin.empty and col_fecha and col_monto:
        mapa_meses = {1: 'enero', 2: 'febrero', 3: 'marzo', 4: 'abril', 5: 'mayo', 6: 'junio', 
                      7: 'julio', 8: 'agosto', 9: 'septiembre', 10: 'octubre', 11: 'noviembre', 12: 'diciembre'}
        
        df_fin['Fecha_dt'] = pd.to_datetime(df_fin[col_fecha], dayfirst=True, errors='coerce')
        df_fin['Mes_Nombre'] = df_fin['Fecha_dt'].dt.month.map(mapa_meses)
        
        for mes in meses_orden:
            df_mes = df_fin[df_fin['Mes_Nombre'] == mes]
            if not df_mes.empty:
                ingreso_real = df_mes[df_mes[col_monto] > 0][col_monto].sum()
                egreso_real = abs(df_mes[df_mes[col_monto] < 0][col_monto].sum())
            else:
                ingreso_real = 0
                egreso_real = 0
            
            datos_proyeccion.append({"Mes": mes, "Tipo": "Real Ingreso", "Monto": ingreso_real})
            datos_proyeccion.append({"Mes": mes, "Tipo": "Real Egreso", "Monto": egreso_real})

    df_chart = pd.DataFrame(datos_proyeccion)
    
    st.subheader("Evolución Mensual")
    fig = go.Figure()
    
    df_p_in = df_chart[df_chart['Tipo'] == "Proyectado Ingreso"]
    fig.add_trace(go.Scatter(x=df_p_in['Mes'], y=df_p_in['Monto'], name="Meta Facturación", line=dict(color='#00CC96', dash='dot')))
    
    df_p_out = df_chart[df_chart['Tipo'] == "Proyectado Egreso (Fijo)"]
    fig.add_trace(go.Scatter(x=df_p_out['Mes'], y=df_p_out['Monto'], name="Base Costos Fijos", line=dict(color='#EF553B', dash='dot')))
    
    df_r_in = df_chart[df_chart['Tipo'] == "Real Ingreso"]
    fig.add_trace(go.Bar(x=df_r_in['Mes'], y=df_r_in['Monto'], name="Ingreso Real", marker_color='#00CC96', opacity=0.6))
    
    df_r_out = df_chart[df_chart['Tipo'] == "Real Egreso"]
    fig.add_trace(go.Bar(x=df_r_out['Mes'], y=df_r_out['Monto'], name="Gasto Real", marker_color='#EF553B', opacity=0.6))
    
    fig.update_layout(template="plotly_dark", barmode='group', height=500)
    st.plotly_chart(fig, use_container_width=True)

# --- 3. RENTABILIDAD (ACTUALIZADO: Backlog vs Costos) ---
elif "Rentabilidad" in page:
    st.title("💎 Rentabilidad Operativa (Tiempo Real)")
    st.markdown("Calculado cruzando las **Horas Reportadas (Backlog)** con el **Costo Hora (Nómina)**.")

    if df_ops.empty or df_costos.empty:
        st.warning("No hay suficientes datos operativos o de costos para calcular la rentabilidad.")
    else:
        # CRUCE DE DATOS
        # Aseguramos que las llaves sean strings limpios
        df_ops['Consultor'] = df_ops['Consultor'].astype(str).str.strip().str.upper()
        
        # Merge: Unir Backlog con Costos
        df_rent = pd.merge(df_ops, df_costos, left_on='Consultor', right_on='COLABORADOR', how='left')
        
        # Calcular Costo Devengado
        col_costo = next((c for c in df_rent.columns if "Costo Hora" in c), None)
        if col_costo:
            df_rent['Costo_Devengado'] = df_rent['Tiempo real'] * df_rent[col_costo]
            df_rent['Costo_Devengado'] = df_rent['Costo_Devengado'].fillna(0)
            
            # --- MÉTRICAS ---
            total_horas = df_rent['Tiempo real'].sum()
            total_dinero = df_rent['Costo_Devengado'].sum()
            
            m1, m2, m3 = st.columns(3)
            m1.metric("Horas Ejecutadas", f"{total_horas:.1f} h")
            m2.metric("Costo Nómina Devengado", f"${total_dinero:,.0f}")
            m3.metric("Registros Procesados", len(df_rent))
            
            st.divider()
            
            # --- GRÁFICAS ---
            c_left, c_right = st.columns(2)
            
            # 1. Burn Rate Diario
            with c_left:
                st.subheader("🔥 Burn Rate (Costo Diario)")
                if 'Fecha de entrega' in df_rent.columns:
                    df_diario = df_rent.groupby('Fecha de entrega')['Costo_Devengado'].sum().reset_index()
                    fig_burn = px.bar(df_diario, x='Fecha de entrega', y='Costo_Devengado', 
                                      color_discrete_sequence=['#FF4B4B'])
                    fig_burn.update_layout(template="plotly_dark", xaxis_title="Fecha", yaxis_title="Costo ($)")
                    st.plotly_chart(fig_burn, use_container_width=True)
            
            # 2. Costo por Cliente
            with c_right:
                st.subheader("🏢 Costo por Cliente")
                if 'Nombre del cliente' in df_rent.columns:
                    df_cliente = df_rent.groupby('Nombre del cliente')['Costo_Devengado'].sum().reset_index().sort_values('Costo_Devengado', ascending=False)
                    fig_cli = px.bar(df_cliente, y='Nombre del cliente', x='Costo_Devengado', orientation='h',
                                     color='Costo_Devengado', color_continuous_scale='Bluered_r')
                    fig_cli.update_layout(template="plotly_dark", yaxis={'categoryorder':'total ascending'})
                    st.plotly_chart(fig_cli, use_container_width=True)
                    
            with st.expander("Ver Detalle de Datos"):
                st.dataframe(df_rent[['Fecha de entrega', 'Nombre del cliente', 'Consultor', 'Tiempo real', 'Costo_Devengado']])
        else:
            st.error("No se encontró la columna de Costo Hora en el diccionario.")

# --- 4. OPERATIVA ---
elif "Operativa" in page:
    st.title("⚙️ Operativa")
    if not df_ops.empty:
        st.subheader("Mapa de Calor de Esfuerzo (Horas)")
        if 'Consultor' in df_ops.columns and 'Tipo de tarea' in df_ops.columns:
            # Agrupar para limpiar la visualización
            df_tree = df_ops.groupby(['Consultor', 'Tipo de tarea'])['Tiempo real'].sum().reset_index()
            # Filtrar tareas con 0 horas
            df_tree = df_tree[df_tree['Tiempo real'] > 0]
            
            fig = px.treemap(df_tree, path=['Consultor', 'Tipo de tarea'], values='Tiempo real', color='Consultor')
            fig.update_layout(template="plotly_dark")
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("No hay datos operativos cargados.")

# --- 5. COMERCIAL ---
elif "Comercial" in page:
    st.title("📈 Comercial & Proyección")
    st.info("🚧 FASE 5: Próximamente Funnel de Ventas y Runway.")
