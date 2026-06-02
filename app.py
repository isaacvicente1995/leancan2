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
from pdf2image import convert_from_bytes
import pytesseract
from PIL import Image

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
# FUNCIÓN PARA LEER PDF CON OCR
# ============================================
def leer_pdf_con_ocr(archivo_pdf):
    """Lee un PDF escaneado usando OCR (Tesseract)"""
    try:
        # Convertir PDF a imágenes
        st.info("🖼️ Convirtiendo PDF a imágenes...")
        images = convert_from_bytes(archivo_pdf.getvalue(), dpi=200)
        
        texto_completo = ""
        for i, image in enumerate(images):
            st.info(f"📄 Procesando página {i+1} de {len(images)}...")
            # Aplicar OCR a la imagen
            texto_pagina = pytesseract.image_to_string(image, lang='spa+eng')
            texto_completo += texto_pagina + "\n"
        
        return texto_completo if texto_completo.strip() else None
    except Exception as e:
        st.error(f"Error en OCR: {e}")
        return None

# ============================================
# EXTRACCIÓN CON REGEX
# ============================================
def extraer_con_regex(texto):
    """Extrae líneas usando regex"""
    lineas = []
    for linea in texto.split('\n'):
        # Buscar SKU (códigos de 6-10 dígitos)
        sku_match = re.search(r'\b(\d{6,10})\b', linea)
        
        # Buscar cantidades
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

# ============================================
# CARGAR DATOS
# ============================================
with st.spinner("Cargando datos..."):
    maquinas_data = get_data("maquinas")
    clientes_data = get_data("clientes")
    productos_data = get_data("productos")
    pedidos_data = get_data("pedidos")

# ============================================
# MENÚ
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

# ============================================
# MÁQUINAS
# ============================================
elif menu == "⚙️ Máquinas":
    st.header("⚙️ Máquinas")
    for m in maquinas_data:
        st.write(f"🖥️ {m.get('nombre')}: {m.get('velocidad')} latas/min")

# ============================================
# CLIENTES
# ============================================
elif menu == "👥 Clientes":
    st.header("👥 Clientes")
    for c in clientes_data:
        st.write(f"🏢 {c.get('nombre')}: Prioridad {c.get('prioridad')}/10")

# ============================================
# PRODUCTOS
# ============================================
elif menu == "📦 Productos":
    st.header("📦 Productos")
    for p in productos_data:
        st.write(f"📦 {p.get('sku')}: {p.get('nombre')}")

# ============================================
# PEDIDOS
# ============================================
elif menu == "📝 Pedidos":
    st.header("📝 Pedidos")
    for p in pedidos_data:
        st.write(f"📄 {p.get('numero')}: {p.get('cantidad')} latas")

# ============================================
# CARGAR PEDIDO CON OCR
# ============================================
elif menu == "📄 Cargar Pedido":
    st.header("📄 Cargar Pedido")
    
    st.info("""
    **Sube el PDF del pedido** (aunque sea una imagen escaneada)
    - El sistema usará OCR para leer el texto automáticamente
    - Extraerá SKU, cantidades y detectará RT
    """)
    
    archivo_pdf = st.file_uploader("📎 Selecciona el PDF del pedido", type=['pdf'])
    
    if archivo_pdf:
        st.success(f"✅ Archivo cargado: {archivo_pdf.name}")
        
        # Opciones de procesamiento
        usar_ocr = st.checkbox("Usar OCR (para PDFs escaneados)", value=True)
        
        if st.button("🔍 Procesar Pedido", type="primary"):
            with st.spinner("Leyendo PDF con OCR... (puede tomar 30-60 segundos)"):
                if usar_ocr:
                    texto_extraido = leer_pdf_con_ocr(archivo_pdf)
                else:
                    # Intentar extracción normal
                    try:
                        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
                            tmp.write(archivo_pdf.getvalue())
                            tmp_path = tmp.name
                        with open(tmp_path, 'rb') as f:
                            reader = PyPDF2.PdfReader(f)
                            texto_extraido = ""
                            for page in reader.pages:
                                texto_extraido += page.extract_text()
                        os.unlink(tmp_path)
                    except:
                        texto_extraido = None
            
            if texto_extraido:
                st.success(f"✅ Texto extraído ({len(texto_extraido)} caracteres)")
                
                with st.expander("Ver texto extraído (primeros 500 caracteres)"):
                    st.text(texto_extraido[:500])
                
                # Extraer líneas con regex
                lineas = extraer_con_regex(texto_extraido)
                
                if lineas:
                    st.success(f"✅ Se encontraron {len(lineas)} líneas")
                    st.dataframe(pd.DataFrame(lineas), use_container_width=True)
                    
                    total = sum(l['cantidad'] for l in lineas)
                    st.metric("📦 Total latas", f"{total:,}")
                    
                    # Guardar pedido
                    st.subheader("Datos del pedido")
                    col1, col2 = st.columns(2)
                    with col1:
                        pedido_numero = st.text_input("Número de pedido", "OCR_PEDIDO")
                        fecha_entrega = st.date_input("Fecha de entrega", datetime.now())
                    with col2:
                        opciones = [c['nombre'] for c in clientes_data] if clientes_data else ["CLIENTE_TEST"]
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
                        
                        st.success(f"✅ Pedido guardado con {len(lineas)} líneas")
                        st.balloons()
                else:
                    st.error("❌ No se encontraron líneas. Verifica que el PDF tenga el formato correcto.")
            else:
                st.error("❌ No se pudo extraer texto. Prueba con la opción de pegar texto manualmente.")

# ============================================
# IA PLANIFICAR
# ============================================
elif menu == "🤖 IA Planificar":
    st.header("🤖 Planificación con IA")
    st.info("🚧 En desarrollo - Próximamente")
