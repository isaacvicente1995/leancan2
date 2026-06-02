import streamlit as st
import requests
import pandas as pd
from datetime import datetime
import json
from openai import OpenAI

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

st.sidebar.write("🔧 **Diagnóstico**")

# Función para obtener datos con diagnóstico
def get_data(table):
    try:
        url = f"{SUPABASE_URL}/{table}"
        st.sidebar.write(f"Consultando: {table}")
        response = requests.get(url, headers=HEADERS)
        st.sidebar.write(f"Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            st.sidebar.write(f"✅ {table}: {len(data)} registros")
            return data
        else:
            st.sidebar.error(f"❌ Error {response.status_code}: {response.text[:100]}")
            return []
    except Exception as e:
        st.sidebar.error(f"❌ Excepción: {e}")
        return []

def insert_data(table, data):
    try:
        response = requests.post(f"{SUPABASE_URL}/{table}", headers=HEADERS, json=data)
        return response.status_code in [200, 201]
    except:
        return False

def delete_data(table, id_field, id_value):
    try:
        response = requests.delete(f"{SUPABASE_URL}/{table}?{id_field}=eq.{id_value}", headers=HEADERS)
        return response.status_code == 204
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

# ============================================
# CARGAR DATOS INICIALES
# ============================================
st.sidebar.markdown("---")

with st.spinner("Cargando datos..."):
    maquinas_data = get_data("maquinas")
    clientes_data = get_data("clientes")
    productos_data = get_data("productos")
    pedidos_data = get_data("pedidos")

# Mostrar resumen en sidebar
st.sidebar.markdown("### 📊 Datos cargados")
st.sidebar.write(f"🏭 Máquinas: {len(maquinas_data)}")
st.sidebar.write(f"👥 Clientes: {len(clientes_data)}")
st.sidebar.write(f"📦 Productos: {len(productos_data)}")
st.sidebar.write(f"📝 Pedidos: {len(pedidos_data)}")

# ============================================
# MENU
# ============================================
menu = st.sidebar.radio(
    "MENU",
    ["Dashboard", "Maquinas", "Clientes", "Productos", "Pedidos", "IA Planificar"]
)

# ============================================
# DASHBOARD
# ============================================
if menu == "Dashboard":
    st.header("📊 Dashboard")
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("🏭 Máquinas", len(maquinas_data))
    col2.metric("👥 Clientes", len(clientes_data))
    col3.metric("📦 Productos", len(productos_data))
    col4.metric("📝 Pedidos", len(pedidos_data))
    
    if maquinas_data:
        st.subheader("Máquinas")
        st.dataframe(pd.DataFrame(maquinas_data), use_container_width=True)
    
    if pedidos_data:
        st.subheader("Últimos Pedidos")
        st.dataframe(pd.DataFrame(pedidos_data), use_container_width=True)

# ============================================
# MAQUINAS
# ============================================
elif menu == "Maquinas":
    st.header("⚙️ Máquinas")
    
    tab1, tab2 = st.tabs(["📋 Listado", "➕ Nueva"])
    
    with tab1:
        if maquinas_data:
            for m in maquinas_data:
                with st.expander(f"🖥️ {m.get('nombre', 'Sin nombre')}"):
                    col1, col2, col3 = st.columns(3)
                    col1.metric("Velocidad", f"{m.get('velocidad', 0)} latas/min")
                    col2.metric("Capacidad", f"{m.get('capacidad', 0):,} latas/día")
                    col3.metric("Formato", m.get('formato', 'N/A'))
        else:
            st.warning("No hay máquinas registradas")
    
    with tab2:
        with st.form("new_maquina"):
            nombre = st.text_input("Nombre (E1, E2, E3, E5, E8)")
            velocidad = st.number_input("Velocidad (latas/min)", min_value=1, value=100)
            capacidad = st.number_input("Capacidad diaria (latas)", min_value=1, value=30000)
            formato = st.text_input("Formatos compatibles")
            if st.form_submit_button("💾 Guardar"):
                if nombre:
                    insert_data("maquinas", {
                        "nombre": nombre,
                        "velocidad": velocidad,
                        "capacidad": capacidad,
                        "formato": formato
                    })
                    st.rerun()
                else:
                    st.error("El nombre es obligatorio")

# ============================================
# CLIENTES
# ============================================
elif menu == "Clientes":
    st.header("👥 Clientes")
    
    tab1, tab2 = st.tabs(["📋 Listado", "➕ Nuevo"])
    
    with tab1:
        if clientes_data:
            for c in clientes_data:
                with st.expander(f"🏢 {c.get('nombre', 'Sin nombre')}"):
                    col1, col2 = st.columns(2)
                    col1.metric("Prioridad", f"{c.get('prioridad', 5)}/10")
                    col2.metric("Penalización", f"{c.get('penalizacion', 0)} €/día")
        else:
            st.warning("No hay clientes registrados")
    
    with tab2:
        with st.form("new_cliente"):
            nombre = st.text_input("Nombre del cliente")
            prioridad = st.slider("Prioridad (1-10)", 1, 10, 5)
            penalizacion = st.number_input("Penalización (€/día)", min_value=0, value=0)
            if st.form_submit_button("💾 Guardar"):
                if nombre:
                    insert_data("clientes", {
                        "nombre": nombre,
                        "prioridad": prioridad,
                        "penalizacion": penalizacion
                    })
                    st.rerun()
                else:
                    st.error("El nombre es obligatorio")

# ============================================
# PRODUCTOS
# ============================================
elif menu == "Productos":
    st.header("📦 Productos")
    
    tab1, tab2 = st.tabs(["📋 Listado", "➕ Nuevo"])
    
    with tab1:
        if productos_data:
            for p in productos_data:
                with st.expander(f"📦 {p.get('sku', 'Sin SKU')} - {p.get('nombre', 'Sin nombre')}"):
                    col1, col2 = st.columns(2)
                    col1.metric("Formato", p.get('formato', 'N/A'))
                    col2.metric("Familia", p.get('familia', '-'))
        else:
            st.warning("No hay productos registrados")
    
    with tab2:
        with st.form("new_producto"):
            sku = st.text_input("SKU (código único)")
            nombre = st.text_input("Nombre del producto")
            formato = st.selectbox("Formato de lata", ["RR-120", "RR-90", "RO-85", "RT"])
            familia = st.text_input("Familia (opcional)")
            if st.form_submit_button("💾 Guardar"):
                if sku and nombre:
                    insert_data("productos", {
                        "sku": sku,
                        "nombre": nombre,
                        "formato": formato,
                        "familia": familia
                    })
                    st.rerun()
                else:
                    st.error("SKU y nombre son obligatorios")

# ============================================
# PEDIDOS
# ============================================
elif menu == "Pedidos":
    st.header("📝 Pedidos")
    
    if not clientes_data:
        st.warning("⚠️ Primero crea clientes en la sección 'Clientes'")
    elif not productos_data:
        st.warning("⚠️ Primero crea productos en la sección 'Productos'")
    else:
        tab1, tab2 = st.tabs(["📋 Listado", "➕ Nuevo"])
        
        with tab1:
            if pedidos_data:
                clientes_dict = {c.get('id'): c.get('nombre') for c in clientes_data}
                for p in pedidos_data:
                    cliente_nombre = clientes_dict.get(p.get('cliente_id'), "Desconocido")
                    with st.expander(f"📄 Pedido {p.get('numero', 'Sin número')} - {cliente_nombre}"):
                        col1, col2, col3 = st.columns(3)
                        col1.metric("Fecha entrega", p.get('fecha_entrega', 'N/A'))
                        col2.metric("Cantidad", f"{p.get('cantidad', 0):,} latas")
                        col3.metric("Lleva RT", "✅ Sí" if p.get('lleva_rt') else "❌ No")
            else:
                st.info("No hay pedidos registrados")
        
        with tab2:
            with st.form("new_pedido"):
                col1, col2 = st.columns(2)
                with col1:
                    numero = st.text_input("Número de pedido")
                    cliente_dict = {c.get('nombre'): c.get('id') for c in clientes_data}
                    cliente = st.selectbox("Cliente", list(cliente_dict.keys()))
                with col2:
                    fecha = st.date_input("Fecha de entrega", datetime.now())
                    producto_dict = {p.get('sku'): p.get('nombre') for p in productos_data}
                    producto = st.selectbox("Producto", list(producto_dict.keys()))
                    cantidad = st.number_input("Cantidad (latas)", min_value=1, value=10000, step=1000)
                    lleva_rt = st.checkbox("Lleva retráctil (RT)")
                
                if st.form_submit_button("💾 Guardar Pedido"):
                    if numero:
                        insert_data("pedidos", {
                            "numero": numero,
                            "cliente_id": cliente_dict[cliente],
                            "fecha_entrega": str(fecha),
                            "cantidad": cantidad,
                            "producto_sku": producto,
                            "lleva_rt": 1 if lleva_rt else 0
                        })
                        st.rerun()
                    else:
                        st.error("El número de pedido es obligatorio")

# ============================================
# IA PLANIFICAR
# ============================================
elif menu == "IA Planificar":
    st.header("🤖 Planificación con IA DeepSeek")
    
    col1, col2 = st.columns(2)
    col1.info(f"🏭 Máquinas: {len(maquinas_data)}")
    col2.info(f"📝 Pedidos: {len(pedidos_data)}")
    
    if len(maquinas_data) == 0:
        st.error("❌ No hay máquinas registradas. Ve a 'Máquinas' para añadir.")
    elif len(pedidos_data) == 0:
        st.warning("⚠️ No hay pedidos para planificar. Crea algunos pedidos primero.")
    else:
        if st.button("🚀 Ejecutar DeepSeek IA", type="primary"):
            resultado = planificar_con_ia(maquinas_data, pedidos_data, clientes_data, productos_data)
            
            if resultado:
                st.success("✅ Planificación completada")
                
                if 'analisis' in resultado:
                    st.info(f"🧠 {resultado['analisis']}")
                
                st.subheader("📊 Saturación de Máquinas")
                if 'saturacion' in resultado:
                    df_sat = pd.DataFrame(list(resultado['saturacion'].items()), columns=['Máquina', 'Saturación %'])
                    st.bar_chart(df_sat.set_index('Máquina'))
                
                st.subheader("📋 Asignaciones de la IA")
                if 'asignaciones' in resultado:
                    df_asig = pd.DataFrame(resultado['asignaciones'])
                    st.dataframe(df_asig, use_container_width=True)
                    
                    with st.expander("Ver justificaciones detalladas"):
                        for a in resultado['asignaciones']:
                            st.write(f"**{a.get('pedido_numero')}** → {a.get('maquina_asignada')}")
                            st.caption(f"📝 {a.get('justificacion', 'Sin justificación')}")
                            st.markdown("---")
            else:
                st.error("❌ La IA no pudo generar una planificación. Revisa los datos.")
