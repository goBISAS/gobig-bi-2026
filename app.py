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
st.markdown("""
<style>
    .main {background-color: #0e1117;} 
    .stMetric {background-color: #262730; border: 1px solid #444; padding: 10px; border-radius: 5px;}
    div[data-testid="stExpander"] {background-color: #1c1e26; border-radius: 10px;}
</style>
""", unsafe_allow_html=True)

# --- 2. UTILIDADES Y MAPEOS ---

# MAPEO: Para solucionar el problema de nombres en Rentabilidad
MAPA_CONSULTORES = {
    "Jimmy Peña": "JIMMY PEÑA",
    "Alejandra Buriticá": "ALEJANDRA BURITICA",
    "Alejandra Cárdenas": "MARIA ALEJANDRA CARDENAS",
    "Sebastian Saenz": "SEBASTIAN SAENZ"
}

def limpiar_moneda_colombia(serie):
    """Limpia formatos de moneda ($ 1.000,00) a números flotantes."""
    serie = serie.astype(str).str.replace(r'[$\s]', '', regex=True).str.replace('.', '', regex=False).str.replace(',', '.', regex=False)
    return pd.to_numeric(serie, errors='coerce').fillna(0)

def normalizar_mes(texto):
    """Convierte 'Enero 2026' o 'january' a 'enero'."""
    if not isinstance(texto, str): return ""
    texto = texto.lower()
    meses = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
    for m in meses:
        if m in texto:
            return m
    return ""

def get_colombia_holidays_2026():
    return ["2026-01-01", "2026-01-12", "2026-03-23", "2026-03-26", "2026-03-27", "2026-05-01", 
            "2026-05-18", "2026-06-08", "2026-06-15", "2026-06-29", "2026-07-20", "2026-08-07", 
            "2026-08-17", "2026-10-12", "2026-11-02", "2026-11-16", "2026-12-08", "2026-12-25"]

# --- 3. CARGA DE DATOS ---
@st.cache_data(ttl=600)
def load_data(ids):
    json_str = st.secrets["credenciales_json"]
    key_dict = json.loads(json_str, strict=False)
    creds = Credentials.from_service_account_info(key_dict, scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"])
    client = gspread.authorize(creds)
    
    # Abrir Libros Maestros
    sh_fin = client.open_by_key(ids['fin']) # Financiera
    sh_ops = client.open_by_key(ids['ops']) # Operativa

    # --- A. HOJAS FINANCIERAS ---
    
    # 1. Movimientos Reales (Hoja 01)
    df_fin = pd.DataFrame(sh_fin.worksheet("01_Movimientos financieros desde 2026").get_all_records())
    col_monto = next((c for c in df_fin.columns if "Monto" in c or "Valor" in c), None)
    col_fecha = next((c for c in df_fin.columns if "Fecha" in c), None)
    if col_monto: df_fin[col_monto] = limpiar_moneda_colombia(df_fin[col_monto])

    # 2. Facturación Proyectada (Hoja 02)
    df_fact = pd.DataFrame(sh_fin.worksheet("02_Cuadro de facturación desde 2026").get_all_records())
    col_fact_total = next((c for c in df_fact.columns if "Total" in c or "Precio" in c), None)
    col_fact_mes = next((c for c in df_fact.columns if "Mes" in c or "A" in c), df_fact.columns[0]) # Asumimos col A si no encuentra nombre
    if col_fact_total: df_fact[col_fact_total] = limpiar_moneda_colombia(df_fact[col_fact_total])
    # Limpieza de fechas de emisión para cartera
    col_emision = next((c for c in df_fact.columns if "Emisión" in c or "Fecha" in c), None)
    if col_emision: df_fact[col_emision] = pd.to_datetime(df_fact[col_emision], dayfirst=True, errors='coerce')

    # 3. Proveedores Proyectados (Hoja 03)
    try:
        df_prov = pd.DataFrame(sh_fin.worksheet("03_Cuadro de pagos a proveedores desde 2026").get_all_records())
        col_prov_valor = next((c for c in df_prov.columns if "Valor" in c or "Total" in c), None)
        col_prov_mes = df_prov.columns[0] # Asumimos columna A es Mes
        if col_prov_valor: df_prov[col_prov_valor] = limpiar_moneda_colombia(df_prov[col_prov_valor])
    except:
        df_prov = pd.DataFrame() # Si falla o no existe

    # 4. Costos Fijos (Hoja 05)
    try:
        df_fijos = pd.DataFrame(sh_fin.worksheet("05_Costos fijos desde 2026").get_all_records())
        col_fijo = next((c for c in df_fijos.columns if "Monto" in c), None)
        total_fijos_mensual = limpiar_moneda_colombia(df_fijos[col_fijo]).sum() if col_fijo else 0
    except: total_fijos_mensual = 0

    # 5. Diccionario de Costos (Hoja 04)
    try:
        df_costos = pd.DataFrame(sh_fin.worksheet("04_Diccionario de recursos desde 2026").get_all_records())
        col_costo_h = next((c for c in df_costos.columns if "Costo Hora" in c), None)
        if col_costo_h: df_costos[col_costo_h] = limpiar_moneda_colombia(df_costos[col_costo_h])
        df_costos['COLABORADOR'] = df_costos['COLABORADOR'].astype(str).str.strip().str.upper()
    except: df_costos = pd.DataFrame()

    # --- B. HOJAS OPERATIVAS (BACKLOG) ---
    all_tasks = []
    lista_pestanas = list(MAPA_CONSULTORES.keys()) # Usamos el mapa manual para ir a la fija
    
    for pestana in lista_pestanas:
        try:
            raw = sh_ops.worksheet(pestana).get_all_values()
            if len(raw) > 5:
                header = raw[4] # Fila 5 es encabezado
                data = raw[5:]
                df = pd.DataFrame(data, columns=header)
                df['Consultor_Pestana'] = pestana
                df['Consultor_Cruce'] = MAPA_CONSULTORES.get(pestana) # Nombre para cruzar con diccionario
                
                # Limpieza numéricos
                for c in ['Tiempo estimado', 'Tiempo real']:
                    if c in df.columns:
                        df[c] = pd.to_numeric(df[c].astype(str).str.replace(',', '.'), errors='coerce').fillna(0)
                # Limpieza fechas
                if 'Fecha de entrega' in df.columns:
                    df['Fecha de entrega'] = pd.to_datetime(df['Fecha de entrega'], dayfirst=True, errors='coerce')
                
                all_tasks.append(df)
        except: continue
        
    df_ops = pd.concat(all_tasks, ignore_index=True) if all_tasks else pd.DataFrame()

    return {
        "fin": df_fin, "fact": df_fact, "prov": df_prov, "fijos": df_fijos, 
        "costos": df_costos, "ops": df_ops, "total_fijos": total_fijos_mensual
    }

# --- 4. EJECUCIÓN PRINCIPAL ---
IDS = {
    'fin': "1ldntONNpWFgXPcF8VINDKzNAhG_vGMdzGEOESM3aLNU",
    'ops': "1Vl5rhQDi6YooJgjYAF76oOO0aN8rbPtu07giky36wSo"
}

try:
    data = load_data(IDS)
except Exception as e:
    st.error(f"Error cargando datos: {e}")
    st.stop()

# --- 5. INTERFAZ ---
st.sidebar.title("goBIG Intelligence")
page = st.sidebar.radio("Navegación:", ["🏠 Home", "💰 Financiera", "💎 Rentabilidad", "⚙️ Operativa", "📈 Comercial"])

# ==========================
# HOME
# ==========================
if "Home" in page:
    st.title("🏠 Tablero de Control 2026")
    hoy = datetime.now()
    inicio = datetime(2026, 1, 1)
    dias = (hoy - inicio).days + 1
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Día del año", dias, "de 365")
    c2.metric("Costos Fijos Base", f"${data['total_fijos']:,.0f}", "Mensual")
    c3.metric("Facturación Enero", "Ver Financiera", "Proyección")

# ==========================
# FINANCIERA (CORREGIDA)
# ==========================
elif "Financiera" in page:
    st.title("💰 Financiera: Control Total")
    
    # --- 1. PREPARACIÓN DE DATOS (12 MESES) ---
    meses_orden = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
    df_master = pd.DataFrame({"Mes": months_idx, "Nombre": meses_orden} for months_idx, meses_orden in enumerate(meses_orden, 1))
    
    chart_data = []

    # A. PROYECCIONES (Facturación, Proveedores, Fijos)
    col_mes_fact = data['fact'].columns[0] # Asumimos col A
    col_total_fact = next((c for c in data['fact'].columns if "Total" in c or "Precio" in c), None)
    
    col_mes_prov = data['prov'].columns[0] if not data['prov'].empty else None
    col_val_prov = next((c for c in data['prov'].columns if "Valor" in c), None)

    for mes in meses_orden:
        # Facturación
        val_fact = 0
        if not data['fact'].empty and col_total_fact:
            # Filtramos buscando el string del mes (ej "enero") en la columna A
            mask = data['fact'][col_mes_fact].astype(str).apply(normalizar_mes) == mes
            val_fact = data['fact'][mask][col_total_fact].sum()
            
        # Proveedores
        val_prov = 0
        if not data['prov'].empty and col_mes_prov and col_val_prov:
            mask_p = data['prov'][col_mes_prov].astype(str).apply(normalizar_mes) == mes
            val_prov = data['prov'][mask_p][col_val_prov].sum()

        chart_data.append({"Mes": mes, "Tipo": "1. Meta Facturación", "Monto": val_fact})
        chart_data.append({"Mes": mes, "Tipo": "2. Proveedores (Proy)", "Monto": val_prov})
        # Fijos (Se asume constante todos los meses, o se puede personalizar si hay tabla mensual)
        chart_data.append({"Mes": mes, "Tipo": "3. Costos Fijos Base", "Monto": data['total_fijos']})

    # B. REALIDAD (Movimientos Banco)
    df_fin = data['fin']
    col_monto_fin = next((c for c in df_fin.columns if "Monto" in c or "Valor" in c), None)
    col_fecha_fin = next((c for c in df_fin.columns if "Fecha" in c), None)

    if not df_fin.empty and col_fecha_fin:
        df_fin['Fecha_dt'] = pd.to_datetime(df_fin[col_fecha_fin], dayfirst=True, errors='coerce')
        df_fin['Mes_Nombre'] = df_fin['Fecha_dt'].apply(lambda x: meses_orden[x.month-1] if pd.notnull(x) else "")
        
        for mes in meses_orden:
            df_m = df_fin[df_fin['Mes_Nombre'] == mes]
            ingreso_real = df_m[df_m[col_monto_fin] > 0][col_monto_fin].sum()
            egreso_real = abs(df_m[df_m[col_monto_fin] < 0][col_monto_fin].sum())
            
            chart_data.append({"Mes": mes, "Tipo": "4. Ingreso Real", "Monto": ingreso_real})
            chart_data.append({"Mes": mes, "Tipo": "5. Egreso Real Total", "Monto": egreso_real})

    df_chart = pd.DataFrame(chart_data)

    # --- 2. GRÁFICA PRINCIPAL ---
    st.subheader("📊 Evolución Anual: Plan vs. Realidad")
    fig = go.Figure()
    
    # Líneas de Proyección
    colores = {"1. Meta Facturación": "#00CC96", "2. Proveedores (Proy)": "#FECB52", "3. Costos Fijos Base": "#EF553B"}
    for tipo in ["1. Meta Facturación", "3. Costos Fijos Base", "2. Proveedores (Proy)"]:
        df_t = df_chart[df_chart['Tipo'] == tipo]
        fig.add_trace(go.Scatter(x=df_t['Mes'], y=df_t['Monto'], name=tipo, line=dict(color=colores[tipo], dash='dot')))

    # Barras de Realidad
    df_real_in = df_chart[df_chart['Tipo'] == "4. Ingreso Real"]
    fig.add_trace(go.Bar(x=df_real_in['Mes'], y=df_real_in['Monto'], name="Ingreso Real (Banco)", marker_color='#00CC96', opacity=0.4))
    
    df_real_out = df_chart[df_chart['Tipo'] == "5. Egreso Real Total"]
    fig.add_trace(go.Bar(x=df_real_out['Mes'], y=df_real_out['Monto'], name="Gasto Real (Banco)", marker_color='#EF553B', opacity=0.4))

    fig.update_layout(template="plotly_dark", barmode='overlay', height=500)
    st.plotly_chart(fig, use_container_width=True)

    # --- 3. SECCIONES INFERIORES ---
    c_left, c_right = st.columns([1, 2])
    
    with c_left:
        st.subheader("🍩 Distribución de Gastos (Real)")
        if not df_fin.empty:
            # Filtramos solo egresos
            df_gastos = df_fin[df_fin[col_monto_fin] < 0].copy()
            df_gastos['AbsMonto'] = df_gastos[col_monto_fin].abs()
            
            # Buscamos columna de categoría o concepto
            col_cat = next((c for c in df_gastos.columns if "Cat" in c or "Concepto" in c or "Desc" in c), df_gastos.columns[0])
            
            fig_donut = px.pie(df_gastos, values='AbsMonto', names=col_cat, hole=0.4)
            fig_donut.update_layout(template="plotly_dark", showlegend=False)
            st.plotly_chart(fig_donut, use_container_width=True)
            
            # RST PROVISION
            st.divider()
            st.subheader("⚖️ Provisión Impuestos (RST)")
            mes_actual = datetime.now().month
            nombre_mes_actual = meses_orden[mes_actual-1]
            
            # Buscamos lo facturado este mes
            facturado_mes = df_chart[(df_chart['Mes'] == nombre_mes_actual) & (df_chart['Tipo'] == "1. Meta Facturación")]['Monto'].sum()
            provision = facturado_mes * 0.08 # 8% PROMEDIO RST
            
            st.metric(f"Facturado {nombre_mes_actual.title()}", f"${facturado_mes:,.0f}")
            st.metric(f"Ahorrar para DIAN (8%)", f"${provision:,.0f}", delta="No te gastes esto")
        else:
            st.info("No hay movimientos financieros para generar el gráfico.")

    with c_right:
        st.subheader("⏳ Cartera (Cuentas por Cobrar)")
        if not data['fact'].empty:
            df_cartera = data['fact'].copy()
            # Asumimos columnas básicas
            col_estado = next((c for c in df_cartera.columns if "Status" in c or "Estado" in c), None)
            col_cliente = next((c for c in df_cartera.columns if "Cliente" in c), df_cartera.columns[1])
            col_emision = next((c for c in df_cartera.columns if "Emisión" in c or "Fecha" in c), None)
            
            if col_estado and col_emision:
                # Filtramos NO Pagadas
                pendientes = df_cartera[df_cartera[col_estado].astype(str).str.lower() != "pagada"].copy()
                
                if not pendientes.empty:
                    today = pd.Timestamp.now()
                    pendientes['Días Desde Emisión'] = (today - pendientes[col_emision]).dt.days
                    pendientes['Estado Cartera'] = pendientes['Días Desde Emisión'].apply(lambda x: f"🚨 Vencida ({x-30} días)" if x > 30 else f"✅ Al día (Faltan {30-x})")
                    
                    st.dataframe(
                        pendientes[[col_cliente, col_total_fact, col_emision, 'Estado Cartera']].sort_values(col_emision),
                        use_container_width=True,
                        hide_index=True
                    )
                else:
                    st.success("¡Excelente! No hay facturas pendientes de pago.")
            else:
                st.warning("No se encontraron columnas de 'Estado' o 'Fecha Emisión' en la hoja de facturación.")

# ==========================
# RENTABILIDAD
# ==========================
elif "Rentabilidad" in page:
    st.title("💎 Rentabilidad Operativa (Burn Rate)")
    # ... (Código optimizado de Rentabilidad igual al anterior) ...
    if data['ops'].empty:
        st.error("No hay datos operativos.")
    else:
        df_rent = pd.merge(data['ops'], data['costos'], left_on='Consultor_Cruce', right_on='COLABORADOR', how='left')
        col_costo = next((c for c in df_rent.columns if "Costo Hora" in c), None)
        
        if col_costo:
            df_rent['Costo_Devengado'] = df_rent['Tiempo real'] * df_rent[col_costo]
            total_dinero = df_rent['Costo_Devengado'].sum()
            st.metric("Costo Nómina Enero (Devengado)", f"${total_dinero:,.0f}")
            
            df_diario = df_rent.groupby('Fecha de entrega')['Costo_Devengado'].sum().reset_index()
            st.subheader("🔥 Evolución de Costo Diario")
            st.plotly_chart(px.bar(df_diario, x='Fecha de entrega', y='Costo_Devengado', color_discrete_sequence=['#FF4B4B']), use_container_width=True)

# ==========================
# OPERATIVA
# ==========================
elif "Operativa" in page:
    st.title("⚙️ Operativa")
    if not data['ops'].empty:
        st.subheader("Mapa de Calor de Esfuerzo")
        df_tree = data['ops'][data['ops']['Tiempo real'] > 0]
        fig = px.treemap(df_tree, path=['Consultor_Pestana', 'Tipo de tarea'], values='Tiempo real', color='Consultor_Pestana')
        fig.update_layout(template="plotly_dark")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("Sin datos operativos.")

elif "Comercial" in page:
    st.title("📈 Comercial")
    st.info("Próximamente...")
