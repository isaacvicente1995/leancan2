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

# CSS
st.markdown("""
<style>
    .stApp { background-color: #f0f2f6; }
    h1 { color: #1a365d !important; border-bottom: 3px solid #2c5282 !important; padding-bottom: 15px !important; }
    .metric-card { background: linear-gradient(135deg, #1e3a5f 0%, #2c5282 100%); border-radius: 12px; padding: 20px; color: white; }
    .machine-card { background: white; border-radius: 10px; padding: 15px; margin: 10px 0; border-left: 4px solid; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
    .machine-name { font-size: 20px; font-weight: bold; }
    .stButton > button { background-color: #2c5282; color: white; font-weight: 600; border-radius: 8px; }
    .producto-row { padding: 8px; margin: 5px 0; border-bottom: 1px solid #e2e8f0; }
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
    except:
        return False

def extraer_lineas(texto):
    """Extrae cada línea del pedido (cada SKU con su cantidad)"""
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
            # Extraer nombre del producto
            nombre = linea.replace(sku_match.group(1), '').strip()
            nombre = re.sub(r'\s+', ' ', nombre)[:50]
            lineas.append({
                'sku': sku_match.group(1),
                'nombre': nombre,
                'cantidad': cantidad,
                'lleva_rt': lleva_rt
            })
    return lineas

def asignar_producto_a_maquina(producto):
    """Asigna un producto a la máquina según su formato y RT"""
    if producto['lleva_rt']:
        return 'E5 (Retráctil)'
    else:
        # Por formato (simplificado, se puede mejorar con datos reales)
        sku = producto['sku']
        if sku.startswith('100089') or sku.startswith('560334'):
            return 'E1 / E3 (RR-120)'
        else:
            return 'E2 (Versátil)'

# CARGA DE DATOS
with st.spinner("🔄 Cargando datos..."):
    maquinas = get_data("maquinas")
    clientes = get_data("clientes")
    productos = get_data("productos")
    pedidos = get_data("pedidos")
    clientes_dict = {c['id']: c['nombre'] for c in clientes}
    for p in pedidos:
        p['cliente_nombre'] = clientes_dict.get(p.get('cliente_id', 0), 'Desconocido')

# MENÚ
st.sidebar.markdown("<h2 style='text-align: center; color: white;'>🏭 LeanCan</h2>", unsafe_allow_html=True)
menu = st.sidebar.radio("", ["📊 PANEL DE CONTROL", "🏭 LÍNEAS DE PRODUCCIÓN", "📅 PLANIFICACIÓN", "📦 PEDIDOS", "📄 IMPORTAR PEDIDO"])

# ============================================
# PANEL DE CONTROL
# ============================================
if menu == "📊 PANEL DE CONTROL":
    st.markdown("<h1>📊 Panel de Control</h1>", unsafe_allow_html=True)
    col1, col2, col3, col4 = st.columns(4)
    total_pedidos = len(pedidos)
    total_latas = sum(p.get('cantidad', 0) for p in pedidos)
    pedidos_rt = sum(1 for p in pedidos if p.get('lleva_rt', False))
    
    with col1: st.markdown(f"<div class='metric-card'><h3>📦 PEDIDOS</h3><div class='value'>{total_pedidos}</div></div>", unsafe_allow_html=True)
    with col2: st.markdown(f"<div class='metric-card'><h3>🥫 TOTAL LATAS</h3><div class='value'>{total_latas:,.0f}</div></div>", unsafe_allow_html=True)
    with col3: st.markdown(f"<div class='metric-card'><h3>📦 CON RT</h3><div class='value'>{pedidos_rt}</div></div>", unsafe_allow_html=True)
    with col4: st.markdown(f"<div class='metric-card'><h3>🏭 MÁQUINAS</h3><div class='value'>5</div></div>", unsafe_allow_html=True)

# ============================================
# LÍNEAS DE PRODUCCIÓN
# ============================================
elif menu == "🏭 LÍNEAS DE PRODUCCIÓN":
    st.markdown("<h1>🏭 Líneas de Producción</h1>", unsafe_allow_html=True)
    
    maquinas_info = {
        'E1': {'formato': 'RR-120', 'velocidad': 200, 'capacidad': 54000, 'desc': 'Línea rápida RR-120'},
        'E2': {'formato': 'RR-120/RR-90', 'velocidad': 120, 'capacidad': 32400, 'desc': 'Línea versátil'},
        'E3': {'formato': 'RR-120', 'velocidad': 200, 'capacidad': 54000, 'desc': 'Línea rápida RR-120'},
        'E5': {'formato': 'RT', 'velocidad': 125, 'capacidad': 33750, 'desc': 'Retráctil (solo productos con RT)'},
        'E8': {'formato': 'RO-85', 'velocidad': 180, 'capacidad': 48600, 'desc': 'Línea especial RO-85'}
    }
    
    for maq in ['E1', 'E2', 'E3', 'E5', 'E8']:
        info = maquinas_info[maq]
        st.markdown(f"""
        <div class="machine-card" style="border-left-color: #2c5282;">
            <div><span class="machine-name">{maq}</span> - {info['desc']}</div>
            <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 15px; margin-top: 10px;">
                <div><div style="font-size: 11px;">FORMATO</div><div>{info['formato']}</div></div>
                <div><div style="font-size: 11px;">VELOCIDAD</div><div>{info['velocidad']} latas/min</div></div>
                <div><div style="font-size: 11px;">CAPACIDAD DÍA</div><div>{info['capacidad']:,} latas</div></div>
            </div>
        </div>
        """, unsafe_allow_html=True)

# ============================================
# PLANIFICACIÓN - DIVIDIR PEDIDO POR PRODUCTO
# ============================================
elif menu == "📅 PLANIFICACIÓN":
    st.markdown("<h1>📅 Planificación de Producción</h1>", unsafe_allow_html=True)
    
    if not pedidos:
        st.warning("⚠️ No hay pedidos para planificar. Importa pedidos primero.")
    else:
        st.subheader("📋 Pedidos Cargados")
        
        # Mostrar todos los pedidos agrupados
        df_pedidos = pd.DataFrame(pedidos)
        st.dataframe(df_pedidos[['numero', 'cliente_nombre', 'cantidad', 'fecha_entrega', 'lleva_rt']], use_container_width=True)
        
        st.markdown("---")
        st.subheader("🏭 Asignación de Productos a Máquinas")
        
        # Para cada pedido, dividir por productos y asignar a máquinas
        for pedido in pedidos:
            st.markdown(f"### 📦 Pedido: {pedido['numero']} - {pedido['cliente_nombre']}")
            
            # Aquí necesitaríamos los productos individuales del pedido
            # Por ahora, mostramos el pedido completo con una asignación sugerida
            cantidad = pedido['cantidad']
            lleva_rt = pedido['lleva_rt']
            
            if lleva_rt:
                maquina_asignada = "E5 (Retráctil)"
                capacidad_maquina = 33750
                color = "#d62728"
            else:
                maquina_asignada = "E1 / E3 (RR-120)"
                capacidad_maquina = 54000
                color = "#1f77b4"
            
            st.markdown(f"""
            <div style="background-color: white; border-radius: 10px; padding: 15px; margin: 10px 0; border-left: 4px solid {color};">
                <table style="width: 100%;">
                    <tr>
                        <td style="width: 40%;"><strong>Producto:</strong> {pedido.get('producto_sku', 'N/A')}</td>
                        <td style="width: 20%;"><strong>Cantidad:</strong> {cantidad:,} latas</td>
                        <td style="width: 20%;"><strong>RT:</strong> {"✅ Sí" if lleva_rt else "❌ No"}</td>
                        <td style="width: 20%;"><strong>Máquina:</strong> {maquina_asignada}</td>
                    </tr>
                </table>
            </div>
            """, unsafe_allow_html=True)
        
        st.markdown("---")
        
        # Resumen por máquina
        st.subheader("📊 Resumen de Producción por Máquina")
        
        resumen = {
            'E1/E3 (RR-120)': {'latas': 0, 'pedidos': 0, 'productos': []},
            'E2 (Versátil)': {'latas': 0, 'pedidos': 0, 'productos': []},
            'E5 (Retráctil)': {'latas': 0, 'pedidos': 0, 'productos': []},
            'E8 (RO-85)': {'latas': 0, 'pedidos': 0, 'productos': []}
        }
        
        for pedido in pedidos:
            if pedido['lleva_rt']:
                resumen['E5 (Retráctil)']['latas'] += pedido['cantidad']
                resumen['E5 (Retráctil)']['pedidos'] += 1
                resumen['E5 (Retráctil)']['productos'].append(pedido.get('producto_sku', 'N/A'))
            else:
                resumen['E1/E3 (RR-120)']['latas'] += pedido['cantidad']
                resumen['E1/E3 (RR-120)']['pedidos'] += 1
                resumen['E1/E3 (RR-120)']['productos'].append(pedido.get('producto_sku', 'N/A'))
        
        for maquina, datos in resumen.items():
            if datos['latas'] > 0:
                st.markdown(f"""
                <div class="machine-card" style="border-left-color: #2c5282;">
                    <div><span class="machine-name">{maquina}</span></div>
                    <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 15px; margin-top: 10px;">
                        <div><div style="font-size: 11px;">TOTAL LATAS</div><div style="font-size: 24px; font-weight: bold;">{datos['latas']:,}</div></div>
                        <div><div style="font-size: 11px;">Nº PEDIDOS</div><div style="font-size: 24px; font-weight: bold;">{datos['pedidos']}</div></div>
                        <div><div style="font-size: 11px;">PRODUCTOS</div><div style="font-size: 12px;">{', '.join(set(datos['productos']))}</div></div>
                    </div>
                </div>
                """, unsafe_allow_html=True)

# ============================================
# PEDIDOS
# ============================================
elif menu == "📦 PEDIDOS":
    st.markdown("<h1>📦 Pedidos</h1>", unsafe_allow_html=True)
    
    if pedidos:
        df_ped = pd.DataFrame(pedidos)
        st.dataframe(df_ped[['numero', 'cliente_nombre', 'cantidad', 'fecha_entrega', 'lleva_rt']], use_container_width=True)
    else:
        st.info("No hay pedidos registrados")

# ============================================
# IMPORTAR PEDIDO
# ============================================
elif menu == "📄 IMPORTAR PEDIDO":
    st.markdown("<h1>📄 Importar Pedido</h1>", unsafe_allow_html=True)
    
    st.markdown("""
    <div style="background-color: #e2e8f0; padding: 15px; border-radius: 8px; margin-bottom: 20px;">
        <strong>📋 IMPORTANTE:</strong><br>
        El sistema dividirá el pedido en productos individuales y asignará cada uno a la máquina compatible.
    </div>
    """, unsafe_allow_html=True)
    
    with st.expander("📋 Ver ejemplo - Copia este texto"):
        st.code("""
1000895661880 RR-120 LULAS DE CALDEIRADA S/E 56.000 1 56.000
1000895561883 RR-120 LULAS RECHEADAS CALDEIRADA S/E 35.532 1 35.532
1000898461845 RR-120 POTA GIGANTE EM CALDEIRADA S/E 23.688 1 23.688
1000898461203 RR-120 POTA GIGANTE C/ALHOS/E 5.922 1 5.922
5603344651041 RR-120 LULAS DE CALDEIRADA RT10 GENERAL 220 100 22.000
5603344651058 RR-120 LULAS RECHEADAS EM CALDEIRADA RT10 GENERAL 176 100 17.600
5603344641035 RR-120 POTA GIGANTE EM CALDEIRADA RT10 GENERAL 44 100 4.400
5603344651065 RR-120 CHOQUINHOS RECHEADOS COM TINTA RT10 GENERAL 88 100 8.800
        """)
    
    texto_pedido = st.text_area("📝 Pega aquí el texto del pedido completo:", height=200)
    
    if st.button("🔍 PROCESAR PEDIDO", type="secondary", use_container_width=True):
        if texto_pedido:
            with st.spinner("Dividiendo pedido en productos..."):
                productos = extraer_lineas(texto_pedido)
            
            if productos:
                st.success(f"✅ El pedido se ha dividido en {len(productos)} productos")
                
                # Mostrar cada producto con su máquina asignada
                st.subheader("📦 Productos del Pedido")
                
                for p in productos:
                    maquina = asignar_producto_a_maquina(p)
                    st.markdown(f"""
                    <div style="background-color: white; border-radius: 8px; padding: 10px; margin: 5px 0; border-left: 4px solid #2c5282;">
                        <table style="width: 100%;">
                            <tr>
                                <td style="width: 30%;"><strong>SKU:</strong> {p['sku']}</td>
                                <td style="width: 40%;"><strong>Producto:</strong> {p['nombre'][:40]}</td>
                                <td style="width: 15%;"><strong>Cantidad:</strong> {p['cantidad']:,}</td>
                                <td style="width: 15%;"><strong>Máquina:</strong> {maquina}</td>
                            </tr>
                        </table>
                    </div>
                    """, unsafe_allow_html=True)
                
                # Resumen por máquina
                st.subheader("📊 Resumen por Máquina")
                resumen = {}
                for p in productos:
                    maq = asignar_producto_a_maquina(p)
                    if maq not in resumen:
                        resumen[maq] = {'latas': 0, 'productos': []}
                    resumen[maq]['latas'] += p['cantidad']
                    resumen[maq]['productos'].append(p['sku'])
                
                for maq, datos in resumen.items():
                    st.markdown(f"**{maq}**: {datos['latas']:,} latas - Productos: {', '.join(datos['productos'])}")
                
                st.session_state['productos_pedido'] = productos
            else:
                st.error("❌ No se encontraron productos en el texto")
        else:
            st.warning("⚠️ Pega el texto del pedido primero")
    
    if 'productos_pedido' in st.session_state:
        productos = st.session_state['productos_pedido']
        total_latas = sum(p['cantidad'] for p in productos)
        
        col1, col2 = st.columns(2)
        with col1:
            pedido_numero = st.text_input("Número de pedido", "PEDIDO_NUEVO")
            fecha_entrega = st.date_input("Fecha de entrega", datetime.now() + timedelta(days=7))
        with col2:
            opciones = [c['nombre'] for c in clientes] if clientes else ["CLIENTE_TEST"]
            cliente = st.selectbox("Cliente", opciones)
        
        if st.button("💾 GUARDAR PEDIDO", type="primary", use_container_width=True):
            cliente_id = None
            for c in clientes:
                if c['nombre'] == cliente:
                    cliente_id = c['id']
                    break
            
            if cliente_id is None:
                st.error("❌ Cliente no encontrado")
            else:
                guardados = 0
                for item in productos:
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
                    st.success(f"✅ Pedido guardado con {guardados} productos")
                    st.balloons()
                    time.sleep(1)
                    st.rerun()
