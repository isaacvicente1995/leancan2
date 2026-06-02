import streamlit as st
import requests
import pandas as pd
from datetime import datetime
import json
import re
import base64
from openai import OpenAI

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
# IA VISIÓN CON OPENROUTER (LEE PDF DIRECTAMENTE)
# ============================================
def leer_pdf_con_ia_vision(archivo_pdf):
    """
    Usa OpenRouter con modelo de visión para leer el PDF directamente
    """
    if "OPENROUTER_API_KEY" not in st.secrets:
        st.error("❌ No se encontró OPENROUTER_API_KEY en Secrets")
        return None

    try:
        # Convertir PDF a base64
        pdf_base64 = base64.b64encode(archivo_pdf.getvalue()).decode('utf-8')
        
        client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=st.secrets["OPENROUTER_API_KEY"],
        )
        
        prompt = """Analiza este PDF de un pedido de conservas. Extrae TODAS las líneas de pedido.

Para cada línea, busca:
- SKU: códigos de 6-10 dígitos (ej: 566188, 556188, 3344651041)
- Cantidad: números como 56.000, 35.532, 22.000
- Si lleva RT: si aparece "RT10" o "retractil"

Devuelve SOLO un JSON con este formato:
{
    "lineas": [
        {"sku": "566188", "nombre": "LULAS DE CALDEIRADA", "cantidad": 56000, "lleva_rt": false},
        {"sku": "3344651041", "nombre": "LULAS DE CALDEIRADA RT", "cantidad": 22000, "lleva_rt": true}
    ],
    "total_latas": 173942,
    "cliente_detectado": "RAMIREZ Y CIA"
}

NO añadas texto adicional fuera del JSON."""
        
        # Usar modelo de visión Llama 3.2 (gratuito)
        response = client.chat.completions.create(
            model="meta-llama/llama-3.2-11b-vision-instruct:free",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:application/pdf;base64,{pdf_base64}"
                            }
                        }
                    ]
                }
            ],
            temperature=0.1,
            max_tokens=2000,
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
        
        return json.loads(respuesta.strip())
        
    except Exception as e:
        st.error(f"Error con IA Visión: {e}")
        return None

# ============================================
# MÉTODO DE RESPALDO (REGEX)
# ============================================
def extraer_con_regex(texto):
    """Extrae líneas usando regex (funciona si el PDF tiene texto)"""
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
            nombre = linea.replace(sku_match.group(1), '').strip()[:50]
            lineas.append({
                'sku': sku_match.group(1),
                'nombre': nombre,
                'cantidad': cantidad,
                'lleva_rt': lleva_rt
            })
    return lineas

# Cargar datos
with st.spinner("Cargando datos..."):
    maquinas_data = get_data("maquinas")
    clientes_data = get_data("clientes")
    productos_data = get_data("productos")
    pedidos_data = get_data("pedidos")

# Menú
menu = st.sidebar.radio(
    "MENU",
    ["📊 Dashboard", "⚙️ Máquinas", "👥 Clientes", "📦 Productos", "📝 Pedidos", "📄 IA lee PDF"]
)

# Dashboard
if menu == "📊 Dashboard":
    st.header("📊 Dashboard")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("🏭 Máquinas", len(maquinas_data))
    col2.metric("👥 Clientes", len(clientes_data))
    col3.metric("📦 Productos", len(productos_data))
    col4.metric("📝 Pedidos", len(pedidos_data))

# Máquinas
elif menu == "⚙️ Máquinas":
    st.header("⚙️ Máquinas")
    for m in maquinas_data:
        st.write(f"🖥️ {m.get('nombre')}: {m.get('velocidad')} latas/min")

# Clientes
elif menu == "👥 Clientes":
    st.header("👥 Clientes")
    for c in clientes_data:
        st.write(f"🏢 {c.get('nombre')}: Prioridad {c.get('prioridad')}/10")

# Productos
elif menu == "📦 Productos":
    st.header("📦 Productos")
    for p in productos_data:
        st.write(f"📦 {p.get('sku')}: {p.get('nombre')}")

# Pedidos
elif menu == "📝 Pedidos":
    st.header("📝 Pedidos")
    for p in pedidos_data:
        st.write(f"📄 {p.get('numero')}: {p.get('cantidad')} latas")

# ============================================
# IA LEE PDF
# ============================================
elif menu == "📄 IA lee PDF":
    st.header("🤖 IA lee el PDF automáticamente")
    
    st.info("""
    **Cómo funciona:**
    1. Sube el PDF del pedido
    2. La IA con visión leerá el PDF (aunque sea imagen escaneada)
    3. Extraerá automáticamente SKU, cantidades y detectará RT
    4. Guarda el pedido en la base de datos
    
    *Usa modelo Llama 3.2 Vision (gratuito)*
    """)
    
    archivo_pdf = st.file_uploader("📎 Selecciona el PDF del pedido", type=['pdf'])
    
    if archivo_pdf:
        st.success(f"✅ Archivo cargado: {archivo_pdf.name} ({archivo_pdf.size/1024:.1f} KB)")
        
        if st.button("🧠 IA leer PDF", type="primary"):
            with st.spinner("🔍 IA analizando el PDF... (10-30 segundos)"):
                resultado = leer_pdf_con_ia_vision(archivo_pdf)
            
            if resultado and 'lineas' in resultado:
                st.balloons()
                st.success(f"✅ IA extrajo {len(resultado['lineas'])} líneas")
                
                # Mostrar líneas
                df_lineas = pd.DataFrame(resultado['lineas'])
                st.dataframe(df_lineas, use_container_width=True)
                
                total = resultado.get('total_latas', sum(l['cantidad'] for l in resultado['lineas']))
                st.metric("📦 Total latas", f"{total:,}")
                
                if 'cliente_detectado' in resultado:
                    st.info(f"🏢 Cliente detectado: {resultado['cliente_detectado']}")
                
                # Datos del pedido
                st.subheader("📝 Datos del pedido")
                col1, col2 = st.columns(2)
                with col1:
                    pedido_numero = st.text_input("Número de pedido", "IA_PEDIDO_001")
                    fecha_entrega = st.date_input("Fecha de entrega", datetime.now())
                with col2:
                    opciones = [c['nombre'] for c in clientes_data] if clientes_data else [resultado.get('cliente_detectado', 'CLIENTE')]
                    cliente = st.selectbox("Cliente", opciones)
                
                if st.button("💾 Guardar Pedido", type="primary"):
                    cliente_id = 1
                    for c in clientes_data:
                        if c['nombre'] == cliente:
                            cliente_id = c['id']
                            break
                    
                    for item in resultado['lineas']:
                        insert_data("pedidos", {
                            "numero": pedido_numero,
                            "cliente_id": cliente_id,
                            "fecha_entrega": str(fecha_entrega),
                            "cantidad": item['cantidad'],
                            "producto_sku": item.get('sku', item.get('nombre', 'UNKNOWN')[:20]),
                            "lleva_rt": 1 if item.get('lleva_rt', False) else 0
                        })
                    
                    st.success(f"✅ Pedido guardado con {len(resultado['lineas'])} líneas")
                    st.balloons()
            else:
                st.error("❌ La IA no pudo leer el PDF. ¿El archivo es válido?")
