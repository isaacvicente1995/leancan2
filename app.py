import streamlit as st
import requests
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="LeanCan", page_icon="🥫", layout="wide")

st.title("🥫 LeanCan Scheduler")

# Configuración de Supabase
SUPABASE_URL = "https://nubxhtlertuwmevxzuyd.supabase.co/rest/v1"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im51YnhodGxlcnR1d21ldnh6dXlkIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODAzMTI4ODYsImV4cCI6MjA5NTg4ODg4Nn0.sxXfypXZHyqFnXL1xeXdvVw925C6v-dg9Kg--7KNLWs"

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

# Función para obtener datos
def get_data(table):
    try:
        response = requests.get(f"{SUPABASE_URL}/{table}", headers=HEADERS)
        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"Error {response.status_code}: {response.text}")
            return []
    except Exception as e:
        st.error(f"Error de conexión: {e}")
        return []

# Probar conexión inicial
st.subheader("🔌 Verificando conexión")

response = requests.get(f"{SUPABASE_URL}/maquinas", headers=HEADERS)
if response.status_code == 200:
    st.success("✅ Conectado a Supabase correctamente")
    maquinas = response.json()
    st.write(f"📊 Máquinas encontradas: {len(maquinas)}")
    if maquinas:
        st.dataframe(pd.DataFrame(maquinas))
else:
    st.error(f"❌ Error de conexión: {response.status_code}")
    st.code(response.text)
    st.stop()

# Menú
menu = st.sidebar.radio(
    "📋 Menú",
    ["📊 Dashboard", "⚙️ Máquinas", "👥 Clientes", "📦 Productos", "📝 Pedidos"]
)

# Dashboard
if menu == "📊 Dashboard":
    st.header("📊 Dashboard")
    
    col1, col2, col3 = st.columns(3)
    
    maquinas_data = get_data("maquinas")
    col1.metric("Máquinas", len(maquinas_data))
    
    clientes_data = get_data("clientes")
    col2.metric("Clientes", len(clientes_data))
    
    productos_data = get_data("productos")
    col3.metric("Productos", len(productos_data))
    
    st.subheader("🏭 Máquinas")
    if maquinas_data:
        st.dataframe(pd.DataFrame(maquinas_data), use_container_width=True)

# Máquinas
elif menu == "⚙️ Máquinas":
    st.header("⚙️ Máquinas")
    
    maquinas = get_data("maquinas")
    if maquinas:
        for m in maquinas:
            with st.expander(f"🖥️ {m.get('nombre', 'Sin nombre')}"):
                col1, col2, col3 = st.columns(3)
                col1.write(f"Velocidad: {m.get('velocidad', 0)} latas/min")
                col2.write(f"Capacidad: {m.get('capacidad', 0):,} latas/día")
                col3.write(f"Formato: {m.get('formato', 'N/A')}")

# Clientes
elif menu == "👥 Clientes":
    st.header("👥 Clientes")
    
    clientes = get_data("clientes")
    if clientes:
        for c in clientes:
            with st.expander(f"🏢 {c.get('nombre', 'Sin nombre')}"):
                col1, col2 = st.columns(2)
                col1.write(f"Prioridad: {c.get('prioridad', 5)}/10")
                col2.write(f"Penalización: {c.get('penalizacion', 0)} €/día")

# Productos
elif menu == "📦 Productos":
    st.header("📦 Productos")
    
    productos = get_data("productos")
    if productos:
        for p in productos:
            with st.expander(f"📦 {p.get('sku', 'Sin SKU')} - {p.get('nombre', 'Sin nombre')}"):
                col1, col2 = st.columns(2)
                col1.write(f"Formato: {p.get('formato', 'N/A')}")
                col2.write(f"Familia: {p.get('familia', 'N/A')}")

# Pedidos
elif menu == "📝 Pedidos":
    st.header("📝 Pedidos")
    
    pedidos = get_data("pedidos")
    if pedidos:
        st.dataframe(pd.DataFrame(pedidos), use_container_width=True)
    else:
        st.info("No hay pedidos")
