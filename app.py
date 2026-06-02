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

def supabase_get(table):
    try:
        response = requests.get(f"{SUPABASE_URL}/{table}", headers=HEADERS)
        if response.status_code == 200:
            return response.json()
        return []
    except:
        return []

def supabase_post(table, data):
    try:
        response = requests.post(f"{SUPABASE_URL}/{table}", headers=HEADERS, json=data)
        return response.status_code in [200, 201]
    except:
        return False

# ============================================
# FUNCIONES
# ============================================
def extraer_lineas(texto):
    """Extrae productos del pedido"""
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
                'lleva_rt': lleva_rt
            })
    return lineas

def asignar_maquinas(lineas_pedido):
    """Asigna cada producto a la máquina adecuada"""
    capacidades = {'E1': 54000, 'E2': 32400, 'E3': 54000, 'E5': 33750, 'E8': 48600}
    carga = {'E1': 0, 'E2': 0, 'E3': 0, 'E5': 0, 'E8': 0}
    asignaciones = []
    
    for linea in lineas_pedido:
        cantidad = linea['cantidad']
        lleva_rt = linea.get('lleva_rt', False)
        
        if lleva_rt:
            maquina = 'E5'
            asignaciones.append({
                'sku': linea['sku'],
                'nombre': linea['nombre'],
                'cantidad': cantidad,
                'maquina': maquina,
                'lleva_rt': lleva_rt
            })
            carga[maquina] += cantidad
        else:
            # Distribuir entre E1, E2, E3 según carga actual
            opciones = ['E1', 'E2', 'E3']
            opciones_ordenadas = sorted(opciones, key=lambda m: carga[m])
            maquina = opciones_ordenadas[0]
            asignaciones.append({
                'sku': linea['sku'],
                'nombre': linea['nombre'],
                'cantidad': cantidad,
                'maquina': maquina,
                'lleva_rt': lleva_rt
            })
            carga[maquina] += cantidad
    
    return asignaciones, carga, capacidades

# ============================================
# CARGA DE DATOS
# ============================================
with st.spinner("🔄 Cargando datos..."):
    clientes = supabase_get("clientes")
    pedidos = supabase_get("pedidos")
    lineas_pedido = supabase_get("lineas_pedido")
    asignaciones_db = supabase_get("asignaciones")

# ============================================
# MENÚ
# ============================================
st.sidebar.markdown("<h2 style='text-align: center;'>🏭 LeanCan</h2>", unsafe_allow_html=True)
menu = st.sidebar.radio("", ["📊 PANEL", "🏭 MÁQUINAS", "📅 PLANIFICACIÓN", "📦 PEDIDOS", "📄 IMPORTAR"])

# ============================================
# PANEL
# ============================================
if menu == "📊 PANEL":
    st.markdown("<h1>Panel de Control</h1>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns(3)
    col1.metric("📦 Pedidos", len(pedidos))
    col2.metric("📋 Productos", len(lineas_pedido))
    col3.metric("🥫 Latas", sum(l.get('cantidad', 0) for l in lineas_pedido))
    
    if pedidos:
        st.subheader("Últimos pedidos")
        st.dataframe(pd.DataFrame(pedidos[-5:]), use_container_width=True)

# ============================================
# MÁQUINAS
# ============================================
elif menu == "🏭 MÁQUINAS":
    st.markdown("<h1>Líneas de Producción</h1>", unsafe_allow_html=True)
    
    maquinas_info = {
        'E1': {'formato': 'RR-120', 'velocidad': 200, 'capacidad': 54000},
        'E2': {'formato': 'RR-120/RR-90', 'velocidad': 120, 'capacidad': 32400},
        'E3': {'formato': 'RR-120', 'velocidad': 200, 'capacidad': 54000},
        'E5': {'formato': 'RT (Retráctil)', 'velocidad': 125, 'capacidad': 33750},
        'E8': {'formato': 'RO-85', 'velocidad': 180, 'capacidad': 48600}
    }
    
    for maq, info in maquinas_info.items():
        st.markdown(f"""
        <div class="machine-card">
            <div style="font-size: 20px; font-weight: bold;">{maq}</div>
            <div>📦 Formato: {info['formato']} | ⚡ Velocidad: {info['velocidad']} latas/min | 🏭 Capacidad: {info['capacidad']:,} latas/día</div>
        </div>
        """, unsafe_allow_html=True)

# ============================================
# PLANIFICACIÓN
# ============================================
elif menu == "📅 PLANIFICACIÓN":
    st.markdown("<h1>Planificación de Producción</h1>", unsafe_allow_html=True)
    
    if not lineas_pedido:
        st.warning("⚠️ No hay productos cargados. Importa un pedido primero.")
    else:
        if st.button("🚀 GENERAR PLANIFICACIÓN", type="primary", use_container_width=True):
            with st.spinner("Distribuyendo productos entre máquinas..."):
                asignaciones, cargas, capacidades = asignar_maquinas(lineas_pedido)
            
            st.success(f"✅ {len(asignaciones)} productos asignados")
            
            # Gráfico de carga
            st.subheader("📊 Carga por Máquina")
            df_carga = pd.DataFrame([
                {"Máquina": m, "Latas": cargas[m], "Capacidad": capacidades[m], "%": round(cargas[m]/capacidades[m]*100, 1)}
                for m in cargas
            ])
            fig = px.bar(df_carga, x="Máquina", y="%", text="%", color="%", color_continuous_scale=["green","yellow","red"])
            fig.update_traces(textposition='outside')
            st.plotly_chart(fig, use_container_width=True)
            
            # Tabla de asignaciones
            st.subheader("📋 Asignación por Máquina")
            for maquina in ['E1', 'E2', 'E3', 'E5', 'E8']:
                asig = [a for a in asignaciones if a['maquina'] == maquina]
                if asig:
                    with st.expander(f"🖥️ {maquina} - {cargas[maquina]:,} / {capacidades[maquina]:,} latas ({round(cargas[maquina]/capacidades[maquina]*100,1)}%)"):
                        for a in asig:
                            rt = " (con RT)" if a['lleva_rt'] else ""
                            st.write(f"📦 {a['sku']} - {a['nombre'][:40]}: {a['cantidad']:,} latas{rt}")
            
            # Guardar asignaciones
            if st.button("💾 GUARDAR PLANIFICACIÓN"):
                for a in asignaciones:
                    supabase_post("asignaciones", {
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
        df_ped = pd.DataFrame(pedidos)
        st.dataframe(df_ped[['numero', 'cliente_id', 'fecha_entrega', 'estado']], use_container_width=True)
        
        # Mostrar líneas de cada pedido
        if lineas_pedido:
            st.subheader("📋 Productos por Pedido")
            df_lineas = pd.DataFrame(lineas_pedido)
            st.dataframe(df_lineas[['pedido_id', 'sku', 'nombre', 'cantidad', 'lleva_rt']], use_container_width=True)
    else:
        st.info("No hay pedidos registrados")

# ============================================
# IMPORTAR PEDIDO
# ============================================
elif menu == "📄 IMPORTAR":
    st.markdown("<h1>Importar Pedido</h1>", unsafe_allow_html=True)
    
    with st.expander("📋 Ejemplo - Copia este texto"):
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
    
    col1, col2 = st.columns(2)
    with col1:
        pedido_numero = st.text_input("Número de pedido", "PED_" + datetime.now().strftime("%Y%m%d%H%M%S"))
        fecha_entrega = st.date_input("Fecha de entrega", datetime.now() + timedelta(days=7))
    with col2:
        opciones = [c['nombre'] for c in clientes] if clientes else ["CLIENTE_TEST"]
        cliente = st.selectbox("Cliente", opciones)
    
    if st.button("📥 IMPORTAR PEDIDO", type="primary", use_container_width=True):
        if texto_pedido:
            with st.spinner("Procesando..."):
                lineas = extraer_lineas(texto_pedido)
            
            if lineas:
                st.success(f"✅ {len(lineas)} productos extraídos")
                
                # Obtener cliente_id
                cliente_id = None
                for c in clientes:
                    if c['nombre'] == cliente:
                        cliente_id = c['id']
                        break
                
                if cliente_id is None:
                    st.error("❌ Cliente no encontrado. Ve a Supabase y añade el cliente.")
                else:
                    # Guardar cabecera del pedido
                    pedido_data = {
                        "numero": pedido_numero,
                        "cliente_id": cliente_id,
                        "fecha_entrega": str(fecha_entrega),
                        "estado": "pendiente"
                    }
                    
                    if supabase_post("pedidos", pedido_data):
                        # Obtener el ID del pedido recién creado
                        pedidos_actualizados = supabase_get("pedidos")
                        pedido_id = None
                        for p in pedidos_actualizados:
                            if p['numero'] == pedido_numero:
                                pedido_id = p['id']
                                break
                        
                        if pedido_id:
                            # Guardar cada línea
                            for item in lineas:
                                linea_data = {
                                    "pedido_id": pedido_id,
                                    "sku": item['sku'],
                                    "nombre": item['nombre'],
                                    "cantidad": item['cantidad'],
                                    "lleva_rt": 1 if item['lleva_rt'] else 0
                                }
                                supabase_post("lineas_pedido", linea_data)
                            
                            st.success(f"✅ Pedido {pedido_numero} guardado con {len(lineas)} productos")
                            st.balloons()
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error("No se pudo obtener el ID del pedido")
                    else:
                        st.error("Error al guardar el pedido")
            else:
                st.error("No se encontraron productos")
        else:
            st.warning("Pega el texto del pedido")
