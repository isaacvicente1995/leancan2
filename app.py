import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
import re
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(page_title="LeanCan", page_icon="🥫", layout="wide")

st.title("🥫 LeanCan Scheduler")

# Configuración Supabase
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
    except:
        return False

# ============================================
# FUNCIONES DE PLANIFICACIÓN
# ============================================
def calcular_asignaciones(pedidos, maquinas):
    """Calcula la distribución de pedidos por máquina"""
    asignaciones = []
    
    # Agrupar pedidos por máquina según RT
    for pedido in pedidos:
        maquina = "E5" if pedido.get('lleva_rt', False) else "E1/E3"
        asignaciones.append({
            'pedido_id': pedido.get('id'),
            'pedido_numero': pedido.get('numero'),
            'maquina': maquina,
            'cantidad': pedido.get('cantidad', 0),
            'fecha_entrega': pedido.get('fecha_entrega'),
            'lleva_rt': pedido.get('lleva_rt', False)
        })
    
    return asignaciones

def calcular_saturacion(asignaciones, maquinas):
    """Calcula la saturación de cada máquina"""
    capacidad = {
        'E1': 54000,
        'E2': 32400,
        'E3': 54000,
        'E5': 33750,
        'E8': 48600
    }
    
    carga = {'E1': 0, 'E2': 0, 'E3': 0, 'E5': 0, 'E8': 0}
    
    for asig in asignaciones:
        if asig['maquina'] == 'E5':
            carga['E5'] += asig['cantidad']
        else:
            # Distribuir entre E1 y E3
            if carga['E1'] <= carga['E3']:
                carga['E1'] += asig['cantidad']
            else:
                carga['E3'] += asig['cantidad']
    
    saturacion = {}
    for maq in capacidad:
        saturacion[maq] = round((carga[maq] / capacidad[maq]) * 100, 1)
    
    return saturacion, carga

# ============================================
# FUNCIONES UI
# ============================================
def mostrar_dashboard(maquinas, clientes, productos, pedidos):
    st.header("📊 Dashboard")
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("🏭 Máquinas", len(maquinas))
    col2.metric("👥 Clientes", len(clientes))
    col3.metric("📦 Productos", len(productos))
    col4.metric("📝 Pedidos", len(pedidos))
    
    if pedidos:
        st.subheader("📋 Últimos pedidos")
        df_pedidos = pd.DataFrame(pedidos[-5:])
        st.dataframe(df_pedidos[['numero', 'cantidad', 'fecha_entrega', 'lleva_rt']], use_container_width=True)

def mostrar_equipos(maquinas):
    st.header("🏭 Estado de Equipos")
    
    # Datos de ejemplo (en producción se calcularían de pedidos reales)
    equipos_data = [
        {"nombre": "E1", "formato": "RR-120", "velocidad": 200, "capacidad": 54000, "carga": 65, "color": "#4CAF50"},
        {"nombre": "E2", "formato": "RR-120/RR-90", "velocidad": 120, "capacidad": 32400, "carga": 42, "color": "#2196F3"},
        {"nombre": "E3", "formato": "RR-120", "velocidad": 200, "capacidad": 54000, "carga": 78, "color": "#FF9800"},
        {"nombre": "E5", "formato": "RT (Retráctil)", "velocidad": 125, "capacidad": 33750, "carga": 55, "color": "#9C27B0"},
        {"nombre": "E8", "formato": "RO-85", "velocidad": 180, "capacidad": 48600, "carga": 30, "color": "#E91E63"}
    ]
    
    for equipo in equipos_data:
        with st.container():
            col1, col2, col3, col4, col5 = st.columns([2, 2, 2, 2, 1])
            
            with col1:
                st.subheader(f"🖥️ {equipo['nombre']}")
                st.caption(f"Formato: {equipo['formato']}")
            
            with col2:
                st.metric("⚡ Velocidad", f"{equipo['velocidad']} latas/min")
            
            with col3:
                st.metric("📦 Capacidad", f"{equipo['capacidad']:,} latas/día")
            
            with col4:
                carga = equipo['carga']
                if carga < 50:
                    color_metric = "🟢"
                elif carga < 80:
                    color_metric = "🟡"
                else:
                    color_metric = "🔴"
                st.metric("📊 Carga", f"{color_metric} {carga}%")
                st.progress(carga / 100)
            
            with col5:
                if st.button("Ver", key=f"ver_{equipo['nombre']}"):
                    st.info(f"Línea {equipo['nombre']} - Detalle de producción")
            
            st.markdown("---")

def mostrar_distribucion(pedidos, maquinas):
    st.header("🏭 Distribución de Fabricación")
    
    if not pedidos:
        st.warning("No hay pedidos para distribuir")
        return
    
    # Calcular asignaciones
    asignaciones = calcular_asignaciones(pedidos, maquinas)
    saturacion, carga = calcular_saturacion(asignaciones, maquinas)
    
    # Resumen de distribución
    col1, col2, col3 = st.columns(3)
    
    total_pedidos = len(pedidos)
    total_latas = sum(p.get('cantidad', 0) for p in pedidos)
    pedidos_rt = sum(1 for p in pedidos if p.get('lleva_rt', False))
    
    col1.metric("📋 Total pedidos", total_pedidos)
    col2.metric("📦 Total latas", f"{total_latas:,}")
    col3.metric("📦 Pedidos con RT", pedidos_rt)
    
    st.markdown("---")
    
    # Gráfico de saturación
    st.subheader("📊 Saturación de Máquinas")
    
    df_sat = pd.DataFrame([
        {"Máquina": k, "Saturación %": v, "Capacidad": carga[k]} 
        for k, v in saturacion.items()
    ])
    
    fig = px.bar(df_sat, x="Máquina", y="Saturación %", 
                 text="Saturación %", color="Saturación %",
                 color_continuous_scale=["green", "yellow", "red"],
                 title="Carga de trabajo por máquina")
    fig.update_traces(textposition='outside')
    fig.update_layout(height=400)
    st.plotly_chart(fig, use_container_width=True)
    
    # Tabla de distribución
    st.subheader("📋 Distribución de pedidos por máquina")
    
    # Agrupar por máquina
    distribucion_e1 = [a for a in asignaciones if a['maquina'] == 'E1/E3'][:5]
    distribucion_e5 = [a for a in asignaciones if a['maquina'] == 'E5'][:5]
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 🖥️ Máquinas E1 y E3 (Sin RT)")
        if distribucion_e1:
            df_e1 = pd.DataFrame(distribucion_e1)
            st.dataframe(df_e1[['pedido_numero', 'cantidad', 'fecha_entrega']], use_container_width=True)
            total_e1 = sum(a['cantidad'] for a in distribucion_e1)
            st.caption(f"Total asignado: {total_e1:,} latas")
        else:
            st.info("No hay pedidos asignados a E1/E3")
    
    with col2:
        st.markdown("### 🖥️ Máquina E5 (Con RT)")
        if distribucion_e5:
            df_e5 = pd.DataFrame(distribucion_e5)
            st.dataframe(df_e5[['pedido_numero', 'cantidad', 'fecha_entrega']], use_container_width=True)
            total_e5 = sum(a['cantidad'] for a in distribucion_e5)
            st.caption(f"Total asignado: {total_e5:,} latas")
        else:
            st.info("No hay pedidos con RT")
    
    # Vista Gantt simplificada
    st.subheader("📅 Calendario de producción (Gantt)")
    st.info("Próximamente: Vista Gantt interactiva con arrastrar y soltar")

def extraer_lineas(texto):
    """Extrae líneas del pedido usando regex"""
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
            num = int(c.replace('.', ''))
            if 1000 < num < 1000000:
                cantidad = num
                break
        
        lleva_rt = 'RT10' in linea or 'RT' in linea.upper()
        
        if sku_match and cantidad > 0:
            sku = sku_match.group(1)
            nombre = linea.replace(sku, '').strip()
            nombre = re.sub(r'\s+', ' ', nombre)
            if len(nombre) > 60:
                nombre = nombre[:60]
            
            lineas.append({
                'sku': sku,
                'nombre': nombre,
                'cantidad': cantidad,
                'lleva_rt': lleva_rt
            })
    
    return lineas

# ============================================
# CARGA DE DATOS
# ============================================
with st.spinner("Cargando datos..."):
    maquinas_data = get_data("maquinas")
    clientes_data = get_data("clientes")
    productos_data = get_data("productos")
    pedidos_data = get_data("pedidos")

# ============================================
# MENÚ PRINCIPAL
# ============================================
menu = st.sidebar.radio(
    "📋 MENÚ",
    ["📊 Dashboard", "🏭 Equipos", "📊 Distribución", "📦 Pedidos", "📄 Cargar Pedido"]
)

# ============================================
# PÁGINAS
# ============================================
if menu == "📊 Dashboard":
    mostrar_dashboard(maquinas_data, clientes_data, productos_data, pedidos_data)

elif menu == "🏭 Equipos":
    mostrar_equipos(maquinas_data)

elif menu == "📊 Distribución":
    mostrar_distribucion(pedidos_data, maquinas_data)

elif menu == "📦 Pedidos":
    st.header("📝 Lista de Pedidos")
    if pedidos_data:
        df_pedidos = pd.DataFrame(pedidos_data)
        st.dataframe(df_pedidos, use_container_width=True)
    else:
        st.info("No hay pedidos registrados")

elif menu == "📄 Cargar Pedido":
    st.header("📄 Cargar Pedido")
    
    with st.expander("📋 Ver ejemplo de formato"):
        st.code("""
1000895661880 RR-120 LULAS DE CALDEIRADA S/E 56.000 1 56.000
1000895561883 RR-120 LULAS RECHEADAS CALDEIRADA S/E 35.532 1 35.532
1000898461845 RR-120 POTA GIGANTE EM CALDEIRADA S/E 23.688 1 23.688
5603344651041 RR-120 LULAS DE CALDEIRADA RT10 GENERAL 220 100 22.000
        """)
    
    texto_pedido = st.text_area("Pega aquí el texto del pedido:", height=200)
    
    if st.button("🔍 Procesar Pedido", type="primary"):
        if texto_pedido:
            with st.spinner("Procesando..."):
                lineas = extraer_lineas(texto_pedido)
            
            if lineas:
                st.balloons()
                st.success(f"✅ Se encontraron {len(lineas)} líneas")
                
                df_lineas = pd.DataFrame(lineas)
                st.dataframe(df_lineas, use_container_width=True)
                
                total_latas = sum(l['cantidad'] for l in lineas)
                st.metric("📦 Total latas", f"{total_latas:,}")
                
                col1, col2 = st.columns(2)
                with col1:
                    pedido_numero = st.text_input("Número de pedido", "PEDIDO_NUEVO")
                    fecha_entrega = st.date_input("Fecha de entrega", datetime.now())
                with col2:
                    opciones = [c['nombre'] for c in clientes_data] if clientes_data else ["CLIENTE_TEST"]
                    cliente = st.selectbox("Cliente", opciones)
                
                if st.button("💾 Guardar Pedido", type="primary"):
                    cliente_id = 1
                    for c in clientes_data:
                        if c['nombre'] == cliente:
                            cliente_id = c['id']
                            break
                    
                    for item in lineas:
                        insert_data("pedidos", {
                            "numero": pedido_numero,
                            "cliente_id": cliente_id,
                            "fecha_entrega": str(fecha_entrega),
                            "cantidad": item['cantidad'],
                            "producto_sku": item['sku'],
                            "lleva_rt": 1 if item['lleva_rt'] else 0
                        })
                    
                    st.success(f"✅ Pedido guardado con {len(lineas)} líneas")
                    st.balloons()
            else:
                st.error("No se encontraron líneas")
