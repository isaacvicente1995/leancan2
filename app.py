
import streamlit as st
import requests
import pandas as pd
from datetime import datetime
import json
from openai import OpenAI
import re

st.set_page_config(page_title="LeanCan", page_icon="🥫", layout="wide")

st.title("🥫 LeanCan Scheduler")

# Configuración de Supabase
SUPABASE_URL = "https://nubxhtlertuwmevxzuyd.supabase.co/rest/v1"
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]

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

def planificar_con_ia(maquinas, pedidos, clientes, productos):
    if not maquinas or not pedidos:
        return None

    contexto = f"""
Eres un planificador de produccion en una fabrica de conservas.

## MAQUINAS:
{json.dumps(maquinas, indent=2, ensure_ascii=False)}

## CLIENTES:
{json.dumps(clientes, indent=2, ensure_ascii=False)}

## PRODUCTOS:
{json.dumps(productos, indent=2, ensure_ascii=False)}

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
# CARGAR PEDIDO (NUEVO)
# ============================================
elif menu == "📄 Cargar Pedido":
    st.header("📄 Cargar Pedido desde Texto")
    
    st.info("📝 Copia y pega el texto del pedido (desde PDF o email)")
    
    texto_pedido = st.text_area("Texto del pedido:", height=200)
    
    if texto_pedido:
        lineas = []
        
        for linea in texto_pedido.split('\n'):
            sku_match = re.search(r'\b(\d{6,10})\b', linea)
            cantidades = re.findall(r'\b(\d{1,3}(?:\.\d{3})*|\d{4,})\b', linea)
            cantidad = 0
            for c in cantidades:
                num = int(c.replace('.', ''))
                if 1000 < num < 1000000:
                    cantidad = num
                    break
            
            lleva_rt = 'RT10' in linea or 'retractil' in linea.lower()
            
            if sku_match and cantidad > 0:
                sku = sku_match.group(1)
                lineas.append({
                    'sku': sku,
                    'cantidad': cantidad,
                    'lleva_rt': lleva_rt
                })
        
        if lineas:
            st.success(f"✅ Se encontraron {len(lineas)} líneas")
            st.dataframe(pd.DataFrame(lineas), use_container_width=True)
            
            col1, col2 = st.columns(2)
            with col1:
                pedido_numero = st.text_input("Número de pedido", "RAF2026/206")
                fecha_entrega = st.date_input("Fecha de entrega", datetime.now())
            with col2:
                opciones_clientes = [c['nombre'] for c in clientes_data] if clientes_data else ["RAMIREZ Y CIA"]
                cliente = st.selectbox("Cliente", opciones_clientes)
            
            # Separar por máquinas
            rt_total = sum(l['cantidad'] for l in lineas if l['lleva_rt'])
            normal_total = sum(l['cantidad'] for l in lineas if not l['lleva_rt'])
            
            st.subheader("📋 Propuesta de asignación")
            col_a, col_b, col_c = st.columns(3)
            col_a.metric("E1 + E3 (normal)", f"{normal_total:,} latas")
            col_b.metric("E5 (RT)", f"{rt_total:,} latas")
            col_c.metric("Total", f"{normal_total + rt_total:,} latas")
            
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
                
                st.success(f"✅ Pedido {pedido_numero} guardado con {len(lineas)} líneas")

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
