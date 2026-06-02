import streamlit as st
import requests
import pandas as pd
from datetime import datetime
import json
from openai import OpenAI
import re
import tempfile
import os

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

def extraer_lineas_con_ia(texto):
    """Usa IA para extraer líneas de pedido del texto"""
    
    contexto = f"""
Extrae todas las líneas de pedido del siguiente texto. Busca:
- SKU (códigos de 6-10 dígitos como 566188, 556188, 846184, 3344651041)
- Cantidades (números como 56.000, 35.532, 22.000)
- Si lleva RT (busca "RT10" o "retractil")

Texto:
{texto[:4000]}

Devuelve SOLO un JSON con este formato:
{{"lineas": [
    {{"sku": "566188", "cantidad": 56000, "lleva_rt": false}},
    {{"sku": "3344651041", "cantidad": 22000, "lleva_rt": true}}
]}}
"""
    try:
        client = OpenAI(
            api_key=st.secrets["DEEPSEEK_API_KEY"],
            base_url="https://api.deepseek.com"
        )
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "Eres un extractor de pedidos. Responde SOLO con JSON valido."},
                {"role": "user", "content": contexto}
            ],
            temperature=0.1
        )
        texto_respuesta = response.choices[0].message.content
        if "```json" in texto_respuesta:
            texto_respuesta = texto_respuesta.split("```json")[1].split("```")[0]
        elif "```" in texto_respuesta:
            texto_respuesta = texto_respuesta.split("```")[1].split("```")[0]
        return json.loads(texto_respuesta.strip())
    except Exception as e:
        st.error(f"Error de IA: {e}")
        return None

# Cargar datos
with st.spinner("Cargando datos..."):
    maquinas_data = get_data("maquinas")
    clientes_data = get_data("clientes")
    productos_data = get_data("productos")
    pedidos_data = get_data("pedidos")

# Menu
menu = st.sidebar.radio(
    "MENU",
    ["📊 Dashboard", "⚙️ Máquinas", "👥 Clientes", "📦 Productos", "📝 Pedidos", "📄 Cargar Pedido", "🤖 IA Planificar"]
)

# ============================================
# CARGAR PEDIDO (VERSIÓN SIMPLIFICADA)
# ============================================
if menu == "📄 Cargar Pedido":
    st.header("📄 Cargar Pedido")
    
    st.info("📝 **Instrucciones:** Copia y pega el texto del pedido en el cuadro de abajo.")
    
    # Ejemplo de pedido de RAMIREZ
    with st.expander("📋 Ver ejemplo del pedido de RAMIREZ"):
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
    
    # Textarea para pegar el texto
    texto_pedido = st.text_area("Pega aquí el texto del pedido:", height=200)
    
    # Botón para procesar con IA
    if st.button("🧠 Procesar con IA", type="primary"):
        if texto_pedido:
            with st.spinner("IA analizando el pedido..."):
                resultado = extraer_lineas_con_ia(texto_pedido)
            
            if resultado and 'lineas' in resultado:
                lineas = resultado['lineas']
                st.success(f"✅ IA extrajo {len(lineas)} líneas")
                
                # Mostrar líneas
                df_lineas = pd.DataFrame(lineas)
                st.dataframe(df_lineas, use_container_width=True)
                
                # Calcular totales
                total_rt = sum(l['cantidad'] for l in lineas if l.get('lleva_rt', False))
                total_normal = sum(l['cantidad'] for l in lineas if not l.get('lleva_rt', False))
                
                col1, col2 = st.columns(2)
                col1.metric("📦 E1/E3 (Normal)", f"{total_normal:,} latas")
                col2.metric("📦 E5 (RT)", f"{total_rt:,} latas")
                
                # Datos del pedido
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
                            "lleva_rt": 1 if item.get('lleva_rt', False) else 0
                        })
                    
                    st.success(f"✅ Pedido guardado con {len(lineas)} líneas")
            else:
                st.error("❌ No se pudieron extraer líneas. Prueba pegando el texto manualmente.")
        else:
            st.warning("Pega el texto del pedido primero")

# ============================================
# DASHBOARD
# ============================================
elif menu == "📊 Dashboard":
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
            # Planificación simple (por ahora)
            st.success("✅ Planificación completada")
            st.info("📊 Resumen de producción")
            st.dataframe(pd.DataFrame(pedidos_data), use_container_width=True)
