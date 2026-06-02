import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
import re
import plotly.express as px
import plotly.graph_objects as go
import time

st.set_page_config(
    page_title="LeanCan - Planificación Industrial",
    page_icon="🏭",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS PERSONALIZADO
st.markdown("""
<style>
    .stApp { background-color: #f0f2f6; }
    h1 { color: #1a365d !important; font-weight: 700 !important; border-bottom: 3px solid #2c5282 !important; padding-bottom: 15px !important; }
    .metric-card { background: linear-gradient(135deg, #1e3a5f 0%, #2c5282 100%); border-radius: 12px; padding: 20px; color: white; box-shadow: 0 4px 6px rgba(0,0,0,0.1); margin: 10px 0; }
    .metric-card .value { font-size: 32px; font-weight: bold; }
    .machine-card { background: white; border-radius: 10px; padding: 15px; margin: 10px 0; border-left: 4px solid; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
    .machine-name { font-size: 20px; font-weight: bold; }
    .stButton > button { background-color: #2c5282; color: white; font-weight: 600; border-radius: 8px; }
</style>
""", unsafe_allow_html=True)

# CONFIGURACIÓN SUPABASE
SUPABASE_URL = "https://nubxhtlertuwmevxzuyd.supabase.co/rest/v1"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im51YnhodGxlcnR1d21ldnh6dXlkIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc4MDMxMjg4NiwiZXhwIjoyMDk1ODg4ODg2fQ.pFNHfgUB7Nxz5i3ZDBQtwbC95wvxjs77SwmE_5ROZzw"

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

def get_data(table):
    try:
        response = requests.get(f"{SUPABASE_URL}/{table}", headers=HEADERS)
        if response.status_code == 200:
            return response.json()
        return []
    except:
        return []

def insert_data(table, data):
    try:
        response = requests.post(f"{SUPABASE_URL}/{table}", headers=HEADERS, json=data)
        return response.status_code in [200, 201]
    except Exception as e:
        st.error(f"Error: {e}")
        return False

def extraer_lineas(texto):
    lineas = []
    patron_sku = r'\b(\d{13}|\d{10})\b'
    patron_cantidad = r'\b(\d{1,3}(?:\.\d{3})*|\d{4,})\b'
    
    for linea in texto.split('\n'):
        if not linea.strip():
            continue
        sku_match = re.search(patron_sku, linea)
        cantidades = re.findall(patron_cantidad, linea)
        cantidad = 0
        for c in cantidades:
            try:
                num = int(c.replace('.', ''))
                if 1000 < num < 1000000:
                    cantidad = num
                    break
            except:
                continue
        lleva_rt = 'RT10' in linea or 'RT' in linea.upper()
        if sku_match and cantidad > 0:
            lineas.append({'sku': sku_match.group(1), 'cantidad': cantidad, 'lleva_rt': lleva_rt})
    return lineas

def calcular_carga_real(pedidos):
    capacidades = {'E1': 54000, 'E2': 32400, 'E3': 54000, 'E5': 33750, 'E8': 48600}
    carga = {'E1': 0, 'E2': 0, 'E3': 0, 'E5': 0, 'E8': 0}
    for pedido in pedidos:
        cantidad = pedido.get('cantidad', 0)
        lleva_rt = pedido.get('lleva_rt', False)
        if lleva_rt:
            carga['E5'] += cantidad
        else:
            if carga['E1'] <= carga['E3']:
                carga['E1'] += cantidad
            else:
                carga['E3'] += cantidad
    porcentajes = {maq: round((carga[maq] / capacidades[maq]) * 100, 1) if capacidades[maq] > 0 else 0 for maq in capacidades}
    return carga, porcentajes

def generar_planificacion(pedidos, fecha_inicio, dias=7):
    capacidades = {'E1': 54000, 'E2': 32400, 'E3': 54000, 'E5': 33750, 'E8': 48600}
    plan = {maq: {i: [] for i in range(dias)} for maq in capacidades.keys()}
    carga_diaria = {maq: {i: 0 for i in range(dias)} for maq in capacidades.keys()}
    carga_total = {maq: 0 for maq in capacidades.keys()}
    
    for pedido in sorted(pedidos, key=lambda x: (x.get('fecha_entrega', '9999-12-31'), -x.get('cantidad', 0))):
        cantidad = pedido.get('cantidad', 0)
        lleva_rt = pedido.get('lleva_rt', False)
        pedido_numero = pedido.get('numero', 'N/A')
        maquinas_destino = ['E5'] if lleva_rt else ['E1', 'E3']
        cantidad_restante = cantidad
        for maq in maquinas_destino:
            for dia in range(dias):
                disponible = capacidades[maq] - carga_diaria[maq][dia]
                if disponible <= 0:
                    continue
                asignar = min(cantidad_restante, disponible)
                if asignar > 0:
                    plan[maq][dia].append({'pedido': pedido_numero, 'cantidad': asignar})
                    carga_diaria[maq][dia] += asignar
                    carga_total[maq] += asignar
                    cantidad_restante -= asignar
                    if cantidad_restante <= 0:
                        break
            if cantidad_restante <= 0:
                break
    
    saturacion = {maq: round((carga_total[maq] / (capacidades[maq] * dias)) * 100, 1) for maq in capacidades}
    return plan, saturacion, carga_total

# CARGA DE DATOS
with st.spinner("🔄 Cargando datos..."):
    maquinas = get_data("maquinas")
    clientes = get_data("clientes")
    productos = get_data("productos")
    pedidos = get_data("pedidos")
    clientes_dict = {c['id']: c['nombre'] for c in clientes}
    for p in pedidos:
        p['cliente_nombre'] = clientes_dict.get(p.get('cliente_id', 0), 'Desconocido')

carga_real, porcentaje_carga = calcular_carga_real(pedidos)

# MENÚ
st.sidebar.markdown("<h2 style='text-align: center; color: white;'>🏭 LeanCan</h2>", unsafe_allow_html=True)
menu = st.sidebar.radio("", ["📊 PANEL DE CONTROL", "🏭 LÍNEAS DE PRODUCCIÓN", "📅 PLANIFICACIÓN", "📦 PEDIDOS", "📄 IMPORTAR PEDIDO"])

# PANEL DE CONTROL
if menu == "📊 PANEL DE CONTROL":
    st.markdown("<h1>📊 Panel de Control Industrial</h1>", unsafe_allow_html=True)
    col1, col2, col3, col4 = st.columns(4)
    total_pedidos = len(pedidos)
    total_latas = sum(p.get('cantidad', 0) for p in pedidos)
    pedidos_rt = sum(1 for p in pedidos if p.get('lleva_rt', False))
    
    with col1: st.markdown(f"<div class='metric-card'><h3>📦 PEDIDOS</h3><div class='value'>{total_pedidos}</div></div>", unsafe_allow_html=True)
    with col2: st.markdown(f"<div class='metric-card'><h3>🥫 TOTAL LATAS</h3><div class='value'>{total_latas:,.0f}</div></div>", unsafe_allow_html=True)
    with col3: st.markdown(f"<div class='metric-card'><h3>📦 CON RT</h3><div class='value'>{pedidos_rt}</div></div>", unsafe_allow_html=True)
    with col4: st.markdown(f"<div class='metric-card'><h3>🏭 MÁQUINAS</h3><div class='value'>5</div></div>", unsafe_allow_html=True)

# LÍNEAS DE PRODUCCIÓN
elif menu == "🏭 LÍNEAS DE PRODUCCIÓN":
    st.markdown("<h1>🏭 Líneas de Producción</h1>", unsafe_allow_html=True)
    maquinas_info = {'E1': {'formato': 'RR-120', 'velocidad': 200, 'capacidad': 54000},
                     'E2': {'formato': 'RR-120/RR-90', 'velocidad': 120, 'capacidad': 32400},
                     'E3': {'formato': 'RR-120', 'velocidad': 200, 'capacidad': 54000},
                     'E5': {'formato': 'RT', 'velocidad': 125, 'capacidad': 33750},
                     'E8': {'formato': 'RO-85', 'velocidad': 180, 'capacidad': 48600}}
    
    for maq in ['E1', 'E2', 'E3', 'E5', 'E8']:
        info = maquinas_info[maq]
        carga_actual = porcentaje_carga.get(maq, 0)
        color_border = "#2c5282" if carga_actual < 70 else "#ed8936" if carga_actual < 90 else "#e53e3e"
        st.markdown(f"""
        <div class="machine-card" style="border-left-color: {color_border};">
            <div><span class="machine-name">{maq}</span></div>
            <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 15px;">
                <div><div style="font-size: 11px;">VELOCIDAD</div><div style="font-size: 20px;">{info['velocidad']} <span style="font-size: 12px;">latas/min</span></div></div>
                <div><div style="font-size: 11px;">CAPACIDAD</div><div style="font-size: 20px;">{info['capacidad']:,} <span style="font-size: 12px;">latas/día</span></div></div>
                <div><div style="font-size: 11px;">CARGA</div><div style="font-size: 20px;">{carga_actual}%</div><progress value="{carga_actual}" max="100" style="width: 100%; height: 8px;"></progress></div>
            </div>
        </div>
        """, unsafe_allow_html=True)

# PLANIFICACIÓN
elif menu == "📅 PLANIFICACIÓN":
    st.markdown("<h1>📅 Planificación de Producción</h1>", unsafe_allow_html=True)
    if not pedidos:
        st.warning("⚠️ No hay pedidos")
    else:
        col1, col2 = st.columns([2,1])
        with col1: fecha_inicio = st.date_input("Fecha inicio", datetime.now())
        with col2: dias = st.selectbox("Horizonte", [5,7,10,14], index=1)
        if st.button("GENERAR PLANIFICACIÓN"):
            plan, saturacion, _ = generar_planificacion(pedidos, fecha_inicio, dias)
            df_sat = pd.DataFrame([{"Línea": k, "Saturación": v} for k, v in saturacion.items()])
            fig = px.bar(df_sat, x="Línea", y="Saturación", text="Saturación", color="Saturación", color_continuous_scale=["green","yellow","red"])
            fig.update_traces(textposition='outside')
            st.plotly_chart(fig, use_container_width=True)

# PEDIDOS
elif menu == "📦 PEDIDOS":
    st.markdown("<h1>📦 Pedidos</h1>", unsafe_allow_html=True)
    if pedidos:
        st.dataframe(pd.DataFrame(pedidos), use_container_width=True)
    else:
        st.info("No hay pedidos")

# IMPORTAR PEDIDO
elif menu == "📄 IMPORTAR PEDIDO":
    st.markdown("<h1>📄 Importar Pedido</h1>", unsafe_allow_html=True)
    
    texto_pedido = st.text_area("📝 Texto del pedido:", height=200)
    
    if st.button("🔍 PROCESAR PEDIDO"):
        if texto_pedido:
            lineas = extraer_lineas(texto_pedido)
            if lineas:
                st.success(f"✅ {len(lineas)} líneas extraídas")
                st.dataframe(pd.DataFrame(lineas), use_container_width=True)
                st.session_state['lineas'] = lineas
            else:
                st.error("No se encontraron líneas")
    
    if 'lineas' in st.session_state:
        lineas = st.session_state['lineas']
        total_latas = sum(l['cantidad'] for l in lineas)
        st.metric("Total latas", f"{total_latas:,}")
        
        pedido_numero = st.text_input("Número de pedido", "PEDIDO_NUEVO")
        fecha_entrega = st.date_input("Fecha entrega", datetime.now() + timedelta(days=7))
        cliente = st.selectbox("Cliente", [c['nombre'] for c in clientes] if clientes else ["CLIENTE_TEST"])
        
        if st.button("💾 GUARDAR PEDIDO", type="primary"):
            cliente_id = next((c['id'] for c in clientes if c['nombre'] == cliente), None)
            if cliente_id is None:
                st.error("Cliente no encontrado")
            else:
                guardados = 0
                for item in lineas:
                    if insert_data("pedidos", {
                        "numero": pedido_numero,
                        "cliente_id": cliente_id,
                        "fecha_entrega": str(fecha_entrega),
                        "cantidad": item['cantidad'],
                        "producto_sku": item['sku'],
                        "lleva_rt": 1 if item['lleva_rt'] else 0
                    }):
                        guardados += 1
                if guardados > 0:
                    st.success(f"✅ {guardados} pedidos guardados")
                    st.balloons()
                    time.sleep(1)
                    st.rerun()
