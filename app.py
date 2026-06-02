import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
import re
import plotly.express as px
import time

st.set_page_config(page_title="LeanCan", page_icon="🏭", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #f0f2f6; }
    h1 { color: #1a365d !important; border-bottom: 3px solid #2c5282 !important; }
    .metric-card { background: linear-gradient(135deg, #1e3a5f 0%, #2c5282 100%); border-radius: 12px; padding: 20px; color: white; }
    .machine-card { background: white; border-radius: 10px; padding: 15px; margin: 10px 0; border-left: 4px solid #2c5282; }
    .stButton > button { background-color: #2c5282; color: white; }
</style>
""", unsafe_allow_html=True)

# ============================================
# CONFIGURACIÓN SUPABASE
# ============================================
SUPABASE_URL = "https://nubxhtlertuwmevxzuyd.supabase.co/rest/v1"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im51YnhodGxlcnR1d21ldnh6dXlkIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc4MDMxMjg4NiwiZXhwIjoyMDk1ODg4ODg2fQ.pFNHfgUB7Nxz5i3ZDBQtwbC95wvxjs77SwmE_5ROZzw"

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

def supabase_get(table, filters=None):
    url = f"{SUPABASE_URL}/{table}"
    if filters:
        url += f"?{filters}"
    try:
        resp = requests.get(url, headers=HEADERS)
        return resp.json() if resp.status_code == 200 else []
    except:
        return []

def supabase_post(table, data):
    try:
        resp = requests.post(f"{SUPABASE_URL}/{table}", headers=HEADERS, json=data)
        return resp.status_code in [200, 201]
    except:
        return False

def supabase_delete(table, id_field, id_value):
    try:
        resp = requests.delete(f"{SUPABASE_URL}/{table}?{id_field}=eq.{id_value}", headers=HEADERS)
        return resp.status_code == 204
    except:
        return False

# ============================================
# FUNCIONES DE PLANIFICACIÓN INTELIGENTE
# ============================================
def obtener_compatibilidad(formato, lleva_rt):
    """Devuelve las máquinas compatibles con un producto"""
    if lleva_rt:
        return ['E5']
    
    compatibilidad = {
        'RR-120': ['E1', 'E2', 'E3'],
        'RR-90': ['E2'],
        'RO-85': ['E8'],
        'RT': ['E5']
    }
    return compatibilidad.get(formato, ['E2'])

def distribucion_inteligente(lineas_pedido):
    """
    Distribuye los productos entre máquinas de forma eficiente
    """
    capacidades = {'E1': 54000, 'E2': 32400, 'E3': 54000, 'E5': 33750, 'E8': 48600}
    carga_actual = {'E1': 0, 'E2': 0, 'E3': 0, 'E5': 0, 'E8': 0}
    asignaciones = []
    
    # Ordenar líneas por cantidad (mayor primero) y priorizar RT
    lineas_ordenadas = sorted(lineas_pedido, key=lambda x: (-x.get('cantidad', 0), -x.get('lleva_rt', False)))
    
    for linea in lineas_ordenadas:
        cantidad = linea['cantidad']
        lleva_rt = linea.get('lleva_rt', False)
        formato = linea.get('formato', 'RR-120')
        
        # Obtener máquinas compatibles
        maquinas_posibles = obtener_compatibilidad(formato, lleva_rt)
        
        # Ordenar máquinas por carga actual (menos cargada primero)
        maquinas_ordenadas = sorted(maquinas_posibles, key=lambda m: carga_actual[m])
        
        cantidad_restante = cantidad
        
        for maquina in maquinas_ordenadas:
            if cantidad_restante <= 0:
                break
            
            disponible = capacidades[maquina] - carga_actual[maquina]
            if disponible <= 0:
                continue
            
            asignar = min(cantidad_restante, disponible)
            if asignar > 0:
                asignaciones.append({
                    'linea_id': linea.get('id'),
                    'sku': linea['sku'],
                    'nombre': linea.get('nombre', ''),
                    'maquina': maquina,
                    'cantidad': asignar,
                    'lleva_rt': lleva_rt
                })
                carga_actual[maquina] += asignar
                cantidad_restante -= asignar
        
        # Si no se pudo asignar toda la cantidad, mostrar advertencia
        if cantidad_restante > 0:
            st.warning(f"⚠️ No hay capacidad suficiente para {linea['sku']}: faltan {cantidad_restante} latas")
    
    return asignaciones, carga_actual, capacidades

def extraer_lineas(texto):
    """Extrae líneas del pedido desde texto"""
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
            nombre = linea.replace(sku_match.group(1), '').strip()
            nombre = re.sub(r'\s+', ' ', nombre)[:50]
            lineas.append({
                'sku': sku_match.group(1),
                'nombre': nombre,
                'cantidad': cantidad,
                'lleva_rt': lleva_rt,
                'formato': 'RR-120'  # Por defecto, se puede mejorar
            })
    return lineas

# ============================================
# CARGA DE DATOS
# ============================================
with st.spinner("🔄 Cargando datos..."):
    clientes = supabase_get("clientes")
    pedidos = supabase_get("pedidos")
    lineas_pedido = supabase_get("lineas_pedido")

# Menú
st.sidebar.markdown("<h2 style='text-align: center;'>🏭 LeanCan</h2>", unsafe_allow_html=True)
menu = st.sidebar.radio("", ["📊 PANEL", "🏭 MÁQUINAS", "📅 PLANIFICACIÓN", "📦 PEDIDOS", "📄 IMPORTAR"])

# ============================================
# PANEL
# ============================================
if menu == "📊 PANEL":
    st.markdown("<h1>Panel de Control</h1>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns(3)
    total_pedidos = len(pedidos)
    total_lineas = len(lineas_pedido)
    total_latas = sum(l.get('cantidad', 0) for l in lineas_pedido)
    
    col1.metric("📦 Pedidos", total_pedidos)
    col2.metric("📋 Líneas", total_lineas)
    col3.metric("🥫 Latas", f"{total_latas:,}")
    
    if pedidos:
        st.subheader("Últimos pedidos")
        st.dataframe(pd.DataFrame(pedidos[-5:]), use_container_width=True)

# ============================================
# MÁQUINAS
# ============================================
elif menu == "🏭 MÁQUINAS":
    st.markdown("<h1>Líneas de Producción</h1>", unsafe_allow_html=True)
    
    maquinas_info = {
        'E1': {'formato': 'RR-120', 'velocidad': 200, 'capacidad': 54000, 'color': '#1f77b4'},
        'E2': {'formato': 'RR-120/RR-90', 'velocidad': 120, 'capacidad': 32400, 'color': '#ff7f0e'},
        'E3': {'formato': 'RR-120', 'velocidad': 200, 'capacidad': 54000, 'color': '#2ca02c'},
        'E5': {'formato': 'RT', 'velocidad': 125, 'capacidad': 33750, 'color': '#d62728'},
        'E8': {'formato': 'RO-85', 'velocidad': 180, 'capacidad': 48600, 'color': '#9467bd'}
    }
    
    for maq, info in maquinas_info.items():
        st.markdown(f"""
        <div class="machine-card">
            <div style="font-size: 20px; font-weight: bold;">{maq}</div>
            <div>Formato: {info['formato']} | Velocidad: {info['velocidad']} latas/min | Capacidad: {info['capacidad']:,} latas/día</div>
        </div>
        """, unsafe_allow_html=True)

# ============================================
# PLANIFICACIÓN INTELIGENTE
# ============================================
elif menu == "📅 PLANIFICACIÓN":
    st.markdown("<h1>Planificación Inteligente</h1>", unsafe_allow_html=True)
    
    if not lineas_pedido:
        st.warning("⚠️ No hay líneas de pedido para planificar. Importa un pedido primero.")
    else:
        if st.button("🚀 DISTRIBUIR PRODUCTOS", type="primary", use_container_width=True):
            with st.spinner("Distribuyendo productos entre máquinas..."):
                asignaciones, cargas, capacidades = distribucion_inteligente(lineas_pedido)
            
            st.success(f"✅ {len(asignaciones)} asignaciones generadas")
            
            # Resumen por máquina
            st.subheader("📊 Carga por Máquina")
            
            df_carga = pd.DataFrame([
                {"Máquina": m, "Carga (latas)": cargas[m], "Capacidad": capacidades[m], "%": round(cargas[m]/capacidades[m]*100, 1)}
                for m in cargas
            ])
            
            fig = px.bar(df_carga, x="Máquina", y="%", text="%", color="%", color_continuous_scale=["green","yellow","red"])
            fig.update_traces(textposition='outside')
            st.plotly_chart(fig, use_container_width=True)
            
            # Asignaciones detalladas
            st.subheader("📋 Asignaciones por Máquina")
            
            for maquina in ['E1', 'E2', 'E3', 'E5', 'E8']:
                asig_maquina = [a for a in asignaciones if a['maquina'] == maquina]
                if asig_maquina:
                    with st.expander(f"🖥️ {maquina} - {cargas[maquina]:,} / {capacidades[maquina]:,} latas ({round(cargas[maquina]/capacidades[maquina]*100,1)}%)"):
                        for a in asig_maquina:
                            rt = " (con RT)" if a['lleva_rt'] else ""
                            st.write(f"📦 {a['sku']}: {a['cantidad']:,} latas{rt}")
            
            # Guardar asignaciones en base de datos
            if st.button("💾 GUARDAR PLANIFICACIÓN"):
                for a in asignaciones:
                    supabase_post("asignaciones", {
                        "linea_pedido_id": a.get('linea_id', 0),
                        "maquina": a['maquina'],
                        "cantidad_asignada": a['cantidad'],
                        "fecha_programada": str(datetime.now().date())
                    })
                st.success("Planificación guardada")

# ============================================
# PEDIDOS
# ============================================
elif menu == "📦 PEDIDOS":
    st.markdown("<h1>Pedidos</h1>", unsafe_allow_html=True)
    
    if pedidos:
        for pedido in pedidos:
            with st.expander(f"📄 {pedido.get('numero', 'N/A')}"):
                st.write(f"Cliente: {pedido.get('cliente_id', 'N/A')}")
                st.write(f"Fecha entrega: {pedido.get('fecha_entrega', 'N/A')}")
                
                # Mostrar líneas de este pedido
                lineas = [l for l in lineas_pedido if l.get('pedido_id') == pedido.get('id')]
                if lineas:
                    st.write("**Productos:**")
                    for l in lineas:
                        rt = " (RT)" if l.get('lleva_rt') else ""
                        st.write(f"  - {l.get('sku')}: {l.get('cantidad'):,} latas{rt}")
    else:
        st.info("No hay pedidos")

# ============================================
# IMPORTAR PEDIDO
# ============================================
elif menu == "📄 IMPORTAR":
    st.markdown("<h1>Importar Pedido</h1>", unsafe_allow_html=True)
    
    with st.expander("📋 Ejemplo - Copia este texto"):
        st.code("""
1000895661880 RR-120 LULAS DE CALDEIRADA S/E 56.000 1 56.000
1000895561883 RR-120 LULAS RECHEADAS CALDEIRADA S/E 35.532 1 35.532
5603344651041 RR-120 LULAS DE CALDEIRADA RT10 GENERAL 220 100 22.000
        """)
    
    texto_pedido = st.text_area("📝 Texto del pedido:", height=200)
    
    col1, col2 = st.columns(2)
    with col1:
        pedido_numero = st.text_input("Número de pedido", "PEDIDO_" + datetime.now().strftime("%Y%m%d%H%M%S"))
        fecha_entrega = st.date_input("Fecha de entrega", datetime.now() + timedelta(days=7))
    with col2:
        opciones = [c['nombre'] for c in clientes] if clientes else ["CLIENTE_TEST"]
        cliente = st.selectbox("Cliente", opciones)
    
    if st.button("🔍 PROCESAR Y GUARDAR", type="primary", use_container_width=True):
        if texto_pedido:
            with st.spinner("Procesando pedido..."):
                lineas = extraer_lineas(texto_pedido)
            
            if lineas:
                st.success(f"✅ {len(lineas)} productos extraídos")
                
                # Mostrar productos
                df_lineas = pd.DataFrame(lineas)
                st.dataframe(df_lineas, use_container_width=True)
                
                # Obtener cliente_id
                cliente_id = None
                for c in clientes:
                    if c['nombre'] == cliente:
                        cliente_id = c['id']
                        break
                
                if cliente_id is None:
                    st.error("Cliente no encontrado")
                else:
                    # 1. Guardar cabecera del pedido
                    pedido_data = {
                        "numero": pedido_numero,
                        "cliente_id": cliente_id,
                        "fecha_entrega": str(fecha_entrega),
                        "estado": "pendiente"
                    }
                    
                    if supabase_post("pedidos", pedido_data):
                        # Obtener el ID del pedido recién creado
                        pedidos_nuevos = supabase_get("pedidos", f"numero=eq.{pedido_numero}")
                        if pedidos_nuevos:
                            pedido_id = pedidos_nuevos[0]['id']
                            
                            # 2. Guardar cada línea de pedido
                            for item in lineas:
                                supabase_post("lineas_pedido", {
                                    "pedido_id": pedido_id,
                                    "sku": item['sku'],
                                    "nombre": item['nombre'],
                                    "cantidad": item['cantidad'],
                                    "lleva_rt": item['lleva_rt'],
                                    "formato": "RR-120"
                                })
                            
                            st.success(f"✅ Pedido {pedido_numero} guardado con {len(lineas)} productos")
                            st.balloons()
                            time.sleep(1)
                            st.rerun()
                    else:
                        st.error("Error al guardar el pedido")
            else:
                st.error("No se encontraron productos")
