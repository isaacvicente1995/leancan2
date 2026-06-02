import streamlit as st
import requests
import pandas as pd
from datetime import datetime
import json
import re
import tempfile
import os
from openai import OpenAI
import PyPDF2

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
# FUNCIONES PARA LEER PDF
# ============================================
def extraer_texto_pdf(archivo_pdf):
    """Extrae texto de un PDF usando PyPDF2"""
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
            tmp_file.write(archivo_pdf.getvalue())
            tmp_path = tmp_file.name
        
        texto_completo = ""
        with open(tmp_path, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    texto_completo += page_text + "\n"
        
        os.unlink(tmp_path)
        return texto_completo if texto_completo.strip() else None
    except Exception as e:
        st.error(f"Error al leer PDF: {e}")
        return None

# ============================================
# IA CON OPENROUTER (MODELO DE TEXTO)
# ============================================
def extraer_con_ia(texto_pedido):
    """Usa OpenRouter con modelo de texto para extraer líneas de pedido"""
    if "OPENROUTER_API_KEY" not in st.secrets:
        st.warning("⚠️ No se encontró OPENROUTER_API_KEY. Usando método sin IA.")
        return None

    try:
        client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=st.secrets["OPENROUTER_API_KEY"],
        )
        
        prompt = f"""Extrae todas las líneas de pedido del siguiente texto de un pedido de conservas.

Busca para cada línea:
- SKU: códigos de 6-10 dígitos (ej: 566188, 556188, 3344651041)
- Cantidad: números grandes como 56.000, 35.532, 22.000
- Si lleva RT: si aparece "RT10" o "retractil"

Texto:
{texto_pedido[:4000]}

Devuelve SOLO un JSON válido con este formato:
{{"lineas": [
    {{"sku": "566188", "nombre": "LULAS DE CALDEIRADA", "cantidad": 56000, "lleva_rt": false}},
    {{"sku": "3344651041", "nombre": "LULAS DE CALDEIRADA RT", "cantidad": 22000, "lleva_rt": true}}
]}}
"""
        
        response = client.chat.completions.create(
            model="deepseek/deepseek-chat:free",
            messages=[
                {"role": "system", "content": "Eres un extractor de pedidos. Responde SOLO con JSON válido. No añadas texto fuera del JSON."},
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
        
        return json.loads(respuesta.strip())
        
    except Exception as e:
        st.error(f"Error con IA: {e}")
        return None

# ============================================
# MÉTODO SIN IA (REGEX)
# ============================================
def extraer_con_regex(texto):
    """Extrae líneas usando regex (sin IA, funciona siempre)"""
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
        
        lleva_rt = 'RT10' in linea or 'RT' in linea.upper() or 'retractil' in linea.lower()
        
        if sku_match and cantidad > 0:
            # Limpiar nombre
            nombre = linea.replace(sku_match.group(1), '').strip()
            if len(nombre) > 50:
                nombre = nombre[:50]
            
            lineas.append({
                'sku': sku_match.group(1),
                'nombre': nombre,
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
# MÁQUINAS (SIMPLIFICADO)
# ============================================
elif menu == "⚙️ Máquinas":
    st.header("⚙️ Máquinas")
    for m in maquinas_data:
        st.write(f"🖥️ {m.get('nombre')}: {m.get('velocidad')} latas/min, Cap: {m.get('capacidad'):,} latas/día")

# ============================================
# CLIENTES (SIMPLIFICADO)
# ============================================
elif menu == "👥 Clientes":
    st.header("👥 Clientes")
    for c in clientes_data:
        st.write(f"🏢 {c.get('nombre')}: Prioridad {c.get('prioridad')}/10")

# ============================================
# PRODUCTOS (SIMPLIFICADO)
# ============================================
elif menu == "📦 Productos":
    st.header("📦 Productos")
    for p in productos_data:
        st.write(f"📦 {p.get('sku')}: {p.get('nombre')}")

# ============================================
# PEDIDOS (SIMPLIFICADO)
# ============================================
elif menu == "📝 Pedidos":
    st.header("📝 Pedidos")
    for p in pedidos_data:
        st.write(f"📄 {p.get('numero')}: {p.get('cantidad')} latas | RT: {'✅' if p.get('lleva_rt') else '❌'}")

# ============================================
# CARGAR PEDIDO (PDF + TEXTO + IA)
# ============================================
elif menu == "📄 Cargar Pedido":
    st.header("📄 Cargar Pedido")
    
    st.info("""
    **Dos formas de cargar el pedido:**
    1. 📎 **Subir PDF** - La aplicación leerá el PDF y extraerá el texto
    2. 📝 **Pegar texto** - Si prefieres copiar y pegar manualmente
    """)
    
    # Opción 1: Subir PDF
    st.subheader("📎 Opción 1: Subir archivo PDF")
    archivo_pdf = st.file_uploader("Selecciona el PDF del pedido", type=['pdf'])
    
    texto_extraido = None
    
    if archivo_pdf:
        with st.spinner("Leyendo PDF..."):
            texto_extraido = extraer_texto_pdf(archivo_pdf)
        
        if texto_extraido:
            st.success(f"✅ PDF leído correctamente ({len(texto_extraido)} caracteres)")
            with st.expander("Ver texto extraído del PDF (primeros 500 caracteres)"):
                st.text(texto_extraido[:500])
        else:
            st.error("❌ No se pudo extraer texto del PDF. Puede ser una imagen escaneada. Prueba con la opción de pegar texto.")
    
    # Opción 2: Pegar texto
    st.subheader("📝 Opción 2: Pegar texto manualmente")
    texto_manual = st.text_area("Pega aquí el texto del pedido:", height=150)
    
    # Decidir qué texto usar
    texto_final = texto_extraido if texto_extraido else texto_manual
    
    if texto_final:
        st.subheader("🔧 Procesar pedido")
        
        col1, col2 = st.columns(2)
        with col1:
            usar_ia = st.checkbox("Usar IA (OpenRouter)", value=False, 
                                  help="Más preciso pero consume crédito. Desactiva para usar método rápido sin IA")
        with col2:
            if usar_ia and "OPENROUTER_API_KEY" not in st.secrets:
                st.warning("⚠️ Sin API key. Añade OPENROUTER_API_KEY a Secrets para usar IA")
        
        if st.button("📊 Procesar Pedido", type="primary"):
            with st.spinner("Procesando..." if not usar_ia else "🧠 IA analizando..."):
                if usar_ia and "OPENROUTER_API_KEY" in st.secrets:
                    resultado = extraer_con_ia(texto_final)
                    if resultado and 'lineas' in resultado:
                        lineas = resultado['lineas']
                    else:
                        st.warning("La IA no respondió correctamente. Usando método alternativo...")
                        lineas = extraer_con_regex(texto_final)
                else:
                    lineas = extraer_con_regex(texto_final)
            
            if lineas:
                st.success(f"✅ Se encontraron {len(lineas)} líneas")
                
                df_lineas = pd.DataFrame(lineas)
                st.dataframe(df_lineas, use_container_width=True)
                
                total_rt = sum(l['cantidad'] for l in lineas if l.get('lleva_rt', False))
                total_normal = sum(l['cantidad'] for l in lineas if not l.get('lleva_rt', False))
                
                col1, col2 = st.columns(2)
                col1.metric("📦 Sin RT (E1/E3)", f"{total_normal:,} latas")
                col2.metric("📦 Con RT (E5)", f"{total_rt:,} latas")
                
                st.subheader("Datos del pedido")
                col1, col2 = st.columns(2)
                with col1:
                    pedido_numero = st.text_input("Número de pedido", "RAF2026/206")
                    fecha_entrega = st.date_input("Fecha de entrega", datetime.now())
                with col2:
                    opciones = [c['nombre'] for c in clientes_data] if clientes_data else ["RAMIREZ Y CIA"]
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
                            "lleva_rt": 1 if item.get('lleva_rt', False) else 0
                        })
                    
                    st.success(f"✅ Pedido {pedido_numero} guardado con {len(lineas)} líneas")
                    st.balloons()
            else:
                st.error("❌ No se encontraron líneas. Verifica el formato del texto.")

# ============================================
# IA PLANIFICAR
# ============================================
elif menu == "🤖 IA Planificar":
    st.header("🤖 Planificación con IA")
    st.info("🚧 En desarrollo - Próximamente asignación automática de pedidos a máquinas con IA")
    
    if len(maquinas_data) == 0:
        st.error("❌ No hay máquinas registradas")
    elif len(pedidos_data) == 0:
        st.warning("⚠️ No hay pedidos para planificar")
    else:
        st.write(f"📊 **Resumen actual:** {len(pedidos_data)} pedidos para {len(maquinas_data)} máquinas")
        st.dataframe(pd.DataFrame(pedidos_data), use_container_width=True)
