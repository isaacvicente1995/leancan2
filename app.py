import streamlit as st
import requests
import pandas as pd
from datetime import datetime
import json
from openai import OpenAI
import re
import tempfile
import os
from PyPDF2 import PdfReader

st.set_page_config(page_title="LeanCan", page_icon="🥫", layout="wide")

st.title("🥫 LeanCan Scheduler")

# Configuración de Supabase
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

def extraer_texto_pdf(archivo):
    """Extrae texto de un PDF"""
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
            tmp_file.write(archivo.getvalue())
            tmp_path = tmp_file.name
        
        reader = PdfReader(tmp_path)
        texto_completo = ""
        for page in reader.pages:
            texto_completo += page.extract_text()
        
        os.unlink(tmp_path)
        return texto_completo
    except Exception as e:
        return f"Error al leer PDF: {e}"

def extraer_lineas_con_ia(texto_pdf):
    """Usa IA (DeepSeek) para extraer líneas de pedido del texto"""
    
    contexto = f"""
Extrae todas las líneas de pedido del siguiente texto de un pedido de conservas.

Texto del pedido:
{texto_pdf[:8000]}

Reglas:
1. Busca SKU (códigos de 6-10 dígitos)
2. Busca cantidades (normalmente números grandes como 56.000, 35.532)
3. Detecta si lleva RT (retráctil) - busca "RT10", "RT", "retractil"
4. Extrae el nombre del producto

Devuelve SOLO un JSON con este formato:
{{
    "lineas": [
        {{
            "sku": "566188",
            "nombre": "LULAS DE CALDEIRADA S/E",
            "cantidad": 56000,
            "lleva_rt": false
        }},
        {{
            "sku": "3344651041",
            "nombre": "LULAS DE CALDEIRADA RT10",
            "cantidad": 22000,
            "lleva_rt": true
        }}
    ]
}}
"""
    try:
        client = OpenAI(
            api_key=st.secrets["DEEPSEEK_API_KEY"],
            base_url="https://api.deepseek.com"
        )
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "Eres un extractor de datos de pedidos. Responde SOLO con JSON valido."},
                {"role": "user", "content": contexto}
            ],
            temperature=0.1
        )
        texto = response.choices[0].message.content
        if "```json" in texto:
            texto = texto.split("```json")[1].split("```")[0]
        elif "```" in texto:
            texto = texto.split("```")[1].split("```")[0]
        return json.loads(texto.strip())
    except Exception as e:
        st.error(f"Error de IA: {e}")
        return None

def separar_lineas_trabajo(lineas):
    """Separa líneas por máquina (E1/E3 para normal, E5 para RT)"""
    normales = []
    rt = []
    
    for linea in lineas:
        if linea.get('lleva_rt', False):
            rt.append(linea)
        else:
            normales.append(linea)
    
    return {
        "normales": normales,
        "rt": rt
    }

def planificar_con_ia(maquinas, pedidos, clientes, productos):
    if not maquinas or not pedidos:
        return None

    contexto = f"""
Eres un planificador de produccion en una fabrica de conservas.

## MAQUINAS:
{json.dumps(maquinas, indent=2, ensure_ascii=False)}

## CLIENTES:
{json.dumps(clientes, indent=2, ensure_ascii=False)}

## PEDIDOS:
{json.dumps(pedidos, indent=2, ensure_ascii=False)}

## REGLAS:
1. Asigna cada pedido a una maquina
2. No superar la capacidad diaria
3. Pedidos con RT solo a E5
4. Priorizar clientes con mayor prioridad

Devuelve SOLO JSON:
{{
    "asignaciones": [
        {{"pedido_id": 1, "pedido_numero": "P001", "maquina_asignada": "E1", "justificacion": "texto"}}
    ],
    "saturacion": {{"E1": 45, "E2": 0, "E3": 0, "E5": 30, "E8": 0}},
    "analisis": "Explicacion breve"
}}
"""
    try:
        client = OpenAI(
            api_key=st.secrets["DEEPSEEK_API_KEY"],
            base_url="https://api.deepseek.com"
        )
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "Responde SOLO con JSON valido."},
                {"role": "user", "content": contexto}
            ],
            temperature=0.3
        )
        texto = response.choices[0].message.content
        if "```json" in texto:
            texto = texto.split("```json")[1].split("```")[0]
        elif "```" in texto:
            texto = texto.split("```")[1].split("```")[0]
        return json.loads(texto.strip())
    except Exception as e:
        st.error(f"Error IA: {e}")
        return None

# Cargar datos iniciales
with st.spinner("Cargando datos..."):
    maquinas_data = get_data("maquinas")
    clientes_data = get_data("clientes")
    productos_data = get_data("productos")
    pedidos_data = get_data("pedidos")

# Menu
menu = st.sidebar.radio(
    "MENU",
    ["📊 Dashboard", "⚙️ Máquinas", "👥 Clientes", "📦 Productos", "📝 Pedidos", "📄 Subir PDF con IA", "🤖 IA Planificar"]
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
        st.write(f"🖥️ {m.get('nombre')}: {m.get('velocidad')} latas/min, Cap: {m.get('capacidad'):,} latas/día")

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
        st.write(f"📄 {p.get('numero')}: {p.get('cantidad')} latas | RT: {'✅' if p.get('lleva_rt') else '❌'}")

# ============================================
# SUBIR PDF CON IA (NUEVO)
# ============================================
elif menu == "📄 Subir PDF con IA":
    st.header("📄 Subir PDF y la IA lo separa en líneas de pedido")
    
    st.info("""
    **Cómo funciona:**
    1. Sube el PDF del pedido
    2. La IA (DeepSeek) lee y extrae todas las líneas
    3. Detecta automáticamente SKU, cantidad, y si lleva RT
    4. Separa las líneas por máquina (E1/E3 para normal, E5 para RT)
    5. Guarda el pedido en la base de datos
    """)
    
    archivo_pdf = st.file_uploader("📎 Selecciona el PDF del pedido", type=['pdf'])
    
    if archivo_pdf:
        with st.spinner("📄 Leyendo PDF..."):
            texto_pdf = extraer_texto_pdf(archivo_pdf)
        
        if texto_pdf and "Error" not in texto_pdf:
            st.success(f"✅ PDF leído correctamente ({len(texto_pdf)} caracteres)")
            
            with st.expander("📄 Texto extraído del PDF"):
                st.text(texto_pdf[:1000] + "..." if len(texto_pdf) > 1000 else texto_pdf)
            
            with st.spinner("🧠 IA analizando el pedido..."):
                resultado = extraer_lineas_con_ia(texto_pdf)
            
            if resultado and 'lineas' in resultado:
                lineas = resultado['lineas']
                st.success(f"✅ IA extrajo {len(lineas)} líneas de pedido")
                
                # Mostrar líneas extraídas
                df_lineas = pd.DataFrame(lineas)
                st.subheader("📋 Líneas extraídas")
                st.dataframe(df_lineas, use_container_width=True)
                
                # Separar por máquina
                separacion = separar_lineas_trabajo(lineas)
                
                col1, col2 = st.columns(2)
                with col1:
                    total_normales = sum(l['cantidad'] for l in separacion['normales'])
                    st.metric("E1 / E3 (Sin RT)", f"{total_normales:,} latas")
                    for l in separacion['normales']:
                        st.caption(f"📦 {l['sku']}: {l['cantidad']:,} latas")
                
                with col2:
                    total_rt = sum(l['cantidad'] for l in separacion['rt'])
                    st.metric("E5 (Con RT)", f"{total_rt:,} latas")
                    for l in separacion['rt']:
                        st.caption(f"📦 {l['sku']}: {l['cantidad']:,} latas")
                
                # Datos del pedido
                st.subheader("📝 Datos del pedido")
                col1, col2 = st.columns(2)
                with col1:
                    pedido_numero = st.text_input("Número de pedido", "RAF2026/206")
                    fecha_entrega = st.date_input("Fecha de entrega", datetime.now())
                with col2:
                    opciones_clientes = [c['nombre'] for c in clientes_data] if clientes_data else ["RAMIREZ Y CIA"]
                    cliente = st.selectbox("Cliente", opciones_clientes)
                
                if st.button("💾 Guardar Pedido en Base de Datos", type="primary"):
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
                    
                    # Resumen final
                    st.subheader("📊 Resumen de Producción")
                    total_general = sum(l['cantidad'] for l in lineas)
                    st.metric("Total latas", f"{total_general:,}")
                    st.metric("Para E5 (RT)", f"{total_rt:,}")
                    st.metric("Para E1/E3 (Normal)", f"{total_normales:,}")
            else:
                st.error("❌ La IA no pudo extraer las líneas. Intenta con otro PDF o usa la opción de texto manual.")
        else:
            st.error(f"❌ {texto_pdf}")

# ============================================
# IA PLANIFICAR
# ============================================
elif menu == "🤖 IA Planificar":
    st.header("🤖 Planificación con IA")
    
    if len(maquinas_data) == 0:
        st.error("❌ No hay máquinas")
    elif len(pedidos_data) == 0:
        st.warning("⚠️ No hay pedidos")
    else:
        if st.button("🚀 Ejecutar IA", type="primary"):
            resultado = planificar_con_ia(maquinas_data, pedidos_data, clientes_data, productos_data)
            if resultado:
                st.success("✅ Planificación completada")
                if 'analisis' in resultado:
                    st.info(f"🧠 {resultado['analisis']}")
                if 'asignaciones' in resultado:
                    st.dataframe(pd.DataFrame(resultado['asignaciones']))
                if 'saturacion' in resultado:
                    st.bar_chart(pd.DataFrame(list(resultado['saturacion'].items()), columns=['Máquina', '%']).set_index('Máquina'))
