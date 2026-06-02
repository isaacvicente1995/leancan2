import streamlit as st
import requests
import pandas as pd
from datetime import datetime
import json
import re
from openai import OpenAI

st.set_page_config(page_title="LeanCan", page_icon="🥫", layout="wide")

st.title("🥫 LeanCan Scheduler")

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
# EXTRACCIÓN CON OPENROUTER (GRATIS)
# ============================================
def extraer_con_openrouter(texto_pedido):
    """
    Usa OpenRouter con modelo gratuito Qwen 3.6
    """
    if "OPENROUTER_API_KEY" not in st.secrets:
        st.error("❌ No se encontró OPENROUTER_API_KEY en Secrets")
        return None

    try:
        client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=st.secrets["OPENROUTER_API_KEY"],
        )
        
        prompt = f"""Extrae todas las líneas de pedido del siguiente texto.
Devuelve SOLO un JSON con este formato:
{{"lineas": [{{"sku": "codigo", "cantidad": numero, "lleva_rt": true/false}}]}}

Texto:
{texto_pedido[:3000]}
"""
        
        response = client.chat.completions.create(
            model="qwen/qwen3.6-plus-preview:free",
            messages=[
                {"role": "system", "content": "Eres un extractor de pedidos. Responde SOLO con JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            extra_headers={
                "HTTP-Referer": "https://leancan2.streamlit.app",
                "X-Title": "LeanCan Scheduler"
            }
        )
        
        respuesta = response.choices[0].message.content
        if "```json" in respuesta:
            respuesta = respuesta.split("```json")[1].split("```")[0]
        elif "```" in respuesta:
            respuesta = respuesta.split("```")[1].split("```")[0]
        
        return json.loads(respuesta)
        
    except Exception as e:
        st.error(f"Error con OpenRouter: {e}")
        return None

def extraer_lineas_sin_ia(texto):
    """Método alternativo: extracción con regex (sin IA, ilimitado)"""
    lineas = []
    for linea in texto.split('\n'):
        sku_match = re.search(r'\b(\d{6,10})\b', linea)
        cant_match = re.findall(r'\b(\d{1,3}(?:\.\d{3})*|\d{4,})\b', linea)
        
        cantidad = 0
        for c in cant_match:
            num = int(c.replace('.', ''))
            if 1000 < num < 1000000:
                cantidad = num
                break
        
        lleva_rt = 'RT10' in linea or 'RT' in linea.upper()
        
        if sku_match and cantidad > 0:
            lineas.append({
                'sku': sku_match.group(1),
                'cantidad': cantidad,
                'lleva_rt': lleva_rt
            })
    return lineas

# ============================================
# CARGAR DATOS INICIALES
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
    "MENU",
    ["📊 Dashboard", "⚙️ Máquinas", "👥 Clientes", "📦 Productos", "📝 Pedidos", "📄 Cargar Pedido", "🤖 IA Planificar"]
)

# ============================================
# DASHBOARD
# ============================================
if menu == "📊 Dashboard":
    st.header("📊 Dashboard")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("🏭 Máquinas", len(maquinas_data))
    col2.metric("👥 Clientes", len(clientes_data))
    col3.metric("📦 Productos", len(productos_data))
    col4.metric("📝 Pedidos", len(pedidos_data))
    
    if pedidos_data:
        st.subheader("Últimos pedidos")
        st.dataframe(pd.DataFrame(pedidos_data[-5:]), use_container_width=True)

# ============================================
# MÁQUINAS
# ============================================
elif menu == "⚙️ Máquinas":
    st.header("⚙️ Máquinas")
    
    tab1, tab2 = st.tabs(["📋 Listado", "➕ Nueva"])
    
    with tab1:
        for m in maquinas_data:
            with st.expander(f"🖥️ {m.get('nombre')}"):
                st.write(f"Velocidad: {m.get('velocidad')} latas/min")
                st.write(f"Capacidad: {m.get('capacidad'):,} latas/día")
                st.write(f"Formato: {m.get('formato')}")
    
    with tab2:
        with st.form("new_maquina"):
            nombre = st.text_input("Nombre (E1, E2, E3, E5, E8)")
            velocidad = st.number_input("Velocidad (latas/min)", min_value=1, value=100)
            capacidad = st.number_input("Capacidad diaria (latas)", min_value=1, value=30000)
            formato = st.text_input("Formato compatible")
            if st.form_submit_button("Guardar"):
                if nombre:
                    insert_data("maquinas", {
                        "nombre": nombre,
                        "velocidad": velocidad,
                        "capacidad": capacidad,
                        "formato": formato
                    })
                    st.rerun()

# ============================================
# CLIENTES
# ============================================
elif menu == "👥 Clientes":
    st.header("👥 Clientes")
    
    tab1, tab2 = st.tabs(["📋 Listado", "➕ Nuevo"])
    
    with tab1:
        for c in clientes_data:
            with st.expander(f"🏢 {c.get('nombre')}"):
                st.write(f"Prioridad: {c.get('prioridad')}/10")
                st.write(f"Penalización: {c.get('penalizacion')} €/día")
    
    with tab2:
        with st.form("new_cliente"):
            nombre = st.text_input("Nombre del cliente")
            prioridad = st.slider("Prioridad (1-10)", 1, 10, 5)
            penalizacion = st.number_input("Penalización (€/día)", min_value=0, value=0)
            if st.form_submit_button("Guardar"):
                if nombre:
                    insert_data("clientes", {
                        "nombre": nombre,
                        "prioridad": prioridad,
                        "penalizacion": penalizacion
                    })
                    st.rerun()

# ============================================
# PRODUCTOS
# ============================================
elif menu == "📦 Productos":
    st.header("📦 Productos")
    
    tab1, tab2 = st.tabs(["📋 Listado", "➕ Nuevo"])
    
    with tab1:
        for p in productos_data:
            with st.expander(f"📦 {p.get('sku')} - {p.get('nombre')}"):
                st.write(f"Formato: {p.get('formato')}")
                st.write(f"Familia: {p.get('familia', '-')}")
    
    with tab2:
        with st.form("new_producto"):
            sku = st.text_input("SKU (código único)")
            nombre = st.text_input("Nombre del producto")
            formato = st.selectbox("Formato de lata", ["RR-120", "RR-90", "RO-85", "RT"])
            familia = st.text_input("Familia (opcional)")
            if st.form_submit_button("Guardar"):
                if sku and nombre:
                    insert_data("productos", {
                        "sku": sku,
                        "nombre": nombre,
                        "formato": formato,
                        "familia": familia
                    })
                    st.rerun()

# ============================================
# PEDIDOS
# ============================================
elif menu == "📝 Pedidos":
    st.header("📝 Pedidos")
    
    if not clientes_data:
        st.warning("⚠️ Primero crea clientes")
    elif not productos_data:
        st.warning("⚠️ Primero crea productos")
    else:
        tab1, tab2 = st.tabs(["📋 Listado", "➕ Nuevo"])
        
        with tab1:
            if pedidos_data:
                for p in pedidos_data:
                    with st.expander(f"📄 {p.get('numero')}"):
                        st.write(f"Fecha: {p.get('fecha_entrega')}")
                        st.write(f"Cantidad: {p.get('cantidad'):,} latas")
                        st.write(f"RT: {'✅ Sí' if p.get('lleva_rt') else '❌ No'}")
            else:
                st.info("No hay pedidos")
        
        with tab2:
            with st.form("new_pedido"):
                col1, col2 = st.columns(2)
                with col1:
                    numero = st.text_input("Número de pedido")
                    cliente_opciones = {c['nombre']: c['id'] for c in clientes_data}
                    cliente = st.selectbox("Cliente", list(cliente_opciones.keys()))
                with col2:
                    fecha = st.date_input("Fecha entrega", datetime.now())
                    producto_opciones = {p['sku']: p['nombre'] for p in productos_data}
                    producto = st.selectbox("Producto", list(producto_opciones.keys()))
                    cantidad = st.number_input("Cantidad (latas)", min_value=1, value=10000)
                    lleva_rt = st.checkbox("Lleva RT")
                
                if st.form_submit_button("Guardar"):
                    insert_data("pedidos", {
                        "numero": numero,
                        "cliente_id": cliente_opciones[cliente],
                        "fecha_entrega": str(fecha),
                        "cantidad": cantidad,
                        "producto_sku": producto,
                        "lleva_rt": 1 if lleva_rt else 0
                    })
                    st.rerun()

# ============================================
# CARGAR PEDIDO CON OPENROUTER
# ============================================
elif menu == "📄 Cargar Pedido":
    st.header("📄 Cargar Pedido con OpenRouter (Gratis)")
    
    st.info("""
    🤖 **OpenRouter - Modelos gratuitos**
    - Usa el modelo Qwen 3.6 (1M contexto)
    - 50 peticiones/día gratis
    - Sin tarjeta de crédito
    """)
    
    with st.expander("📋 Ejemplo - Copia este texto"):
        st.code("""
566188 RR-120 LULAS DE CALDEIRADAS/E 56.000
556188 RR-120 LULAS RECHEADAS CALDEIRADAS/E 35.532
846184 RR-120 POTA GIGANTE EM CALDEIRADAS/E 23.688
846120 RR-120 POTA GIGANTE C/ALHOS/E 5.922
3344651041 RR-120 LULAS DE CALDEIRADART10 GENERAL 22.000
3344651058 RR-120 LULAS RECHEADAS EM CALDEIRADART10 GENERAL 17.600
4641035 RR-120 POTA GIGANTE EM CALDEIRADART10 GENERAL 4.400
3344651065 RR-120 CHOQUINHOS RECHEADOS COM TINTART10 GENERAL 8.800
        """)
    
    texto_pedido = st.text_area("Pega aquí el texto del pedido:", height=200)
    
    col1, col2 = st.columns(2)
    with col1:
        usar_ia = st.checkbox("Usar IA de OpenRouter", value=True, 
                              help="Más preciso, consume petición gratuita. 50 req/día")
    with col2:
        if usar_ia and "OPENROUTER_API_KEY" not in st.secrets:
            st.warning("⚠️ Sin API key. Añade OPENROUTER_API_KEY a Secrets")
    
    if st.button("📊 Procesar Pedido", type="primary"):
        if texto_pedido:
            with st.spinner("Procesando..." if not usar_ia else "🧠 OpenRouter IA analizando..."):
                if usar_ia and "OPENROUTER_API_KEY" in st.secrets:
                    resultado = extraer_con_openrouter(texto_pedido)
                    if resultado and 'lineas' in resultado:
                        lineas = resultado['lineas']
                    else:
                        st.warning("La IA no respondió. Usando método alternativo...")
                        lineas = extraer_lineas_sin_ia(texto_pedido)
                else:
                    lineas = extraer_lineas_sin_ia(texto_pedido)
            
            if lineas:
                st.success(f"✅ Se encontraron {len(lineas)} líneas")
                
                df_lineas = pd.DataFrame(lineas)
                st.dataframe(df_lineas, use_container_width=True)
                
                total_rt = sum(l['cantidad'] for l in lineas if l['lleva_rt'])
                total_normal = sum(l['cantidad'] for l in lineas if not l['lleva_rt'])
                
                col1, col2 = st.columns(2)
                col1.metric("📦 E1/E3 (Normal)", f"{total_normal:,} latas")
                col2.metric("📦 E5 (RT)", f"{total_rt:,} latas")
                
                st.subheader("Datos del pedido")
                col1, col2 = st.columns(2)
                with col1:
                    pedido_numero = st.text_input("Número de pedido", "RAF2026/206")
                    fecha_entrega = st.date_input("Fecha de entrega", datetime.now())
                with col2:
                    opciones = [c['nombre'] for c in clientes_data] if clientes_data else ["RAMIREZ Y CIA"]
                    cliente = st.selectbox("Cliente", opciones)
                
                if st.button("💾 Guardar Pedido"):
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
                    
                    st.success(f"✅ Pedido {pedido_numero} guardado con {len(lineas)} líneas")
                    st.balloons()
            else:
                st.error("❌ No se encontraron líneas.")
        else:
            st.warning("⚠️ Pega el texto del pedido primero")

# ============================================
# IA PLANIFICAR
# ============================================
elif menu == "🤖 IA Planificar":
    st.header("🤖 Planificación con IA")
    st.info("🚧 En desarrollo - Próximamente asignación automática con OpenRouter")
    
    if len(maquinas_data) == 0:
        st.error("❌ No hay máquinas")
    elif len(pedidos_data) == 0:
        st.warning("⚠️ No hay pedidos")
    else:
        st.write(f"📊 **Resumen actual:** {len(pedidos_data)} pedidos para {len(maquinas_data)} máquinas")
        st.dataframe(pd.DataFrame(pedidos_data), use_container_width=True)
