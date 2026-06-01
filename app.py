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

# Funciones de base de datos
def get_data(table):
    response = requests.get(f"{SUPABASE_URL}/{table}", headers=HEADERS)
    if response.status_code == 200:
        return response.json()
    return []

def insert_data(table, data):
    response = requests.post(f"{SUPABASE_URL}/{table}", headers=HEADERS, json=data)
    return response.status_code == 201 or response.status_code == 200

def delete_data(table, id_field, id_value):
    response = requests.delete(f"{SUPABASE_URL}/{table}?{id_field}=eq.{id_value}", headers=HEADERS)
    return response.status_code == 204

# Menú principal
menu = st.sidebar.radio(
    "📋 MENÚ PRINCIPAL",
    ["📊 Dashboard", "⚙️ Máquinas", "👥 Clientes", "📦 Productos", "📝 Pedidos", "🏭 Planificación"]
)

# ============================================
# DASHBOARD
# ============================================
if menu == "📊 Dashboard":
    st.header("📊 Dashboard")
    
    col1, col2, col3, col4 = st.columns(4)
    
    maquinas = get_data("maquinas")
    col1.metric("🏭 Máquinas", len(maquinas))
    
    clientes = get_data("clientes")
    col2.metric("👥 Clientes", len(clientes))
    
    productos = get_data("productos")
    col3.metric("📦 Productos", len(productos))
    
    pedidos = get_data("pedidos")
    col4.metric("📝 Pedidos", len(pedidos))
    
    st.markdown("---")
    
    # Mostrar máquinas
    st.subheader("🏭 Estado de Máquinas")
    if maquinas:
        for m in maquinas:
            col1, col2, col3, col4 = st.columns([2,2,2,1])
            col1.write(f"**{m.get('nombre', 'N/A')}**")
            col2.write(f"⚡ {m.get('velocidad', 0)} latas/min")
            col3.write(f"📦 {m.get('capacidad', 0):,} latas/día")
            col4.write(f"🎯 0%")
        st.caption("La carga de trabajo se calculará cuando haya pedidos asignados")
    else:
        st.info("No hay máquinas registradas. Ve a 'Máquinas' para añadir.")

# ============================================
# MÁQUINAS (CRUD completo)
# ============================================
elif menu == "⚙️ Máquinas":
    st.header("⚙️ Gestión de Máquinas")
    
    tab1, tab2 = st.tabs(["📋 Listado", "➕ Añadir Máquina"])
    
    with tab1:
        maquinas = get_data("maquinas")
        if maquinas:
            for m in maquinas:
                with st.expander(f"🖥️ {m.get('nombre', 'Sin nombre')}"):
                    col1, col2, col3, col4 = st.columns([2,2,2,1])
                    col1.metric("Velocidad", f"{m.get('velocidad', 0)} latas/min")
                    col2.metric("Capacidad diaria", f"{m.get('capacidad', 0):,} latas")
                    col3.metric("Formato", m.get('formato', 'N/A'))
                    if col4.button("🗑️ Eliminar", key=f"del_maq_{m.get('id')}"):
                        if delete_data("maquinas", "id", m.get('id')):
                            st.rerun()
        else:
            st.info("No hay máquinas registradas")
    
    with tab2:
        with st.form("form_maquina"):
            col1, col2 = st.columns(2)
            with col1:
                nombre = st.text_input("Nombre (E1, E2, E3, E5, E8)")
                velocidad = st.number_input("Velocidad (latas/min)", min_value=1, value=100)
            with col2:
                formato = st.text_input("Formatos compatibles", placeholder="Ej: RR-120, RR-90")
                capacidad = st.number_input("Capacidad diaria (latas)", min_value=1, value=30000)
            
            if st.form_submit_button("💾 Guardar Máquina"):
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
# CLIENTES (CRUD completo)
# ============================================
elif menu == "👥 Clientes":
    st.header("👥 Gestión de Clientes")
    
    tab1, tab2 = st.tabs(["📋 Listado", "➕ Añadir Cliente"])
    
    with tab1:
        clientes = get_data("clientes")
        if clientes:
            for c in clientes:
                with st.expander(f"🏢 {c.get('nombre', 'Sin nombre')}"):
                    col1, col2, col3 = st.columns([2,2,1])
                    col1.metric("Prioridad", f"{c.get('prioridad', 5)}/10")
                    col2.metric("Penalización", f"{c.get('penalizacion', 0)} €/día")
                    if col3.button("🗑️ Eliminar", key=f"del_cli_{c.get('id')}"):
                        if delete_data("clientes", "id", c.get('id')):
                            st.rerun()
        else:
            st.info("No hay clientes registrados")
    
    with tab2:
        with st.form("form_cliente"):
            nombre = st.text_input("Nombre del cliente")
            col1, col2 = st.columns(2)
            with col1:
                prioridad = st.slider("Prioridad (1-10)", 1, 10, 5)
                st.caption("10 = máxima prioridad")
            with col2:
                penalizacion = st.number_input("Penalización (€/día retraso)", min_value=0, value=0)
            
            if st.form_submit_button("💾 Guardar Cliente"):
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
# PRODUCTOS (CRUD completo)
# ============================================
elif menu == "📦 Productos":
    st.header("📦 Gestión de Productos")
    
    tab1, tab2 = st.tabs(["📋 Listado", "➕ Añadir Producto"])
    
    with tab1:
        productos = get_data("productos")
        if productos:
            for p in productos:
                with st.expander(f"📦 {p.get('sku', 'Sin SKU')} - {p.get('nombre', 'Sin nombre')}"):
                    col1, col2, col3, col4 = st.columns([1,1,1,1])
                    col1.metric("SKU", p.get('sku', 'N/A'))
                    col2.metric("Formato", p.get('formato', 'N/A'))
                    col3.metric("Familia", p.get('familia', '-'))
                    if col4.button("🗑️ Eliminar", key=f"del_prod_{p.get('sku')}"):
                        if delete_data("productos", "sku", p.get('sku')):
                            st.rerun()
        else:
            st.info("No hay productos registrados")
    
    with tab2:
        with st.form("form_producto"):
            col1, col2 = st.columns(2)
            with col1:
                sku = st.text_input("SKU (código único)")
                nombre = st.text_input("Nombre del producto")
            with col2:
                formato = st.selectbox("Formato de lata", ["RR-120", "RR-90", "RO-85", "RT"])
                familia = st.text_input("Familia", placeholder="Ej: TROZOS, SARDINILLA, TUNIDO")
            
            if st.form_submit_button("💾 Guardar Producto"):
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
# PEDIDOS (CRUD completo)
# ============================================
elif menu == "📝 Pedidos":
    st.header("📝 Gestión de Pedidos")
    
    clientes = get_data("clientes")
    productos = get_data("productos")
    
    if not clientes:
        st.warning("⚠️ Primero crea clientes en la sección 'Clientes'")
    elif not productos:
        st.warning("⚠️ Primero crea productos en la sección 'Productos'")
    else:
        tab1, tab2 = st.tabs(["📋 Listado", "➕ Nuevo Pedido"])
        
        with tab1:
            pedidos = get_data("pedidos")
            if pedidos:
                clientes_dict = {c.get('id'): c.get('nombre') for c in clientes}
                for ped in pedidos:
                    cliente_nombre = clientes_dict.get(ped.get('cliente_id'), "Desconocido")
                    with st.expander(f"📄 Pedido {ped.get('numero', 'Sin número')} - {cliente_nombre}"):
                        col1, col2, col3, col4 = st.columns(4)
                        col1.metric("Fecha entrega", ped.get('fecha_entrega', 'N/A'))
                        col2.metric("Cantidad", f"{ped.get('cantidad', 0):,} latas")
                        col3.metric("Producto", ped.get('producto_sku', 'N/A'))
                        col4.metric("Lleva RT", "✅ Sí" if ped.get('lleva_rt') else "❌ No")
                        if st.button("🗑️ Eliminar", key=f"del_ped_{ped.get('id')}"):
                            if delete_data("pedidos", "id", ped.get('id')):
                                st.rerun()
            else:
                st.info("No hay pedidos registrados")
        
        with tab2:
            with st.form("form_pedido"):
                col1, col2 = st.columns(2)
                with col1:
                    numero = st.text_input("Número de pedido")
                    cliente_opciones = {c.get('nombre'): c.get('id') for c in clientes}
                    cliente_nombre = st.selectbox("Cliente", list(cliente_opciones.keys()))
                with col2:
                    fecha_entrega = st.date_input("Fecha de entrega", datetime.now())
                    producto_opciones = {p.get('sku'): p.get('nombre') for p in productos}
                    producto_sku = st.selectbox("Producto", list(producto_opciones.keys()))
                    cantidad = st.number_input("Cantidad (latas)", min_value=1, value=10000, step=1000)
                    lleva_rt = st.checkbox("Lleva retráctil (RT)")
                
                if st.form_submit_button("💾 Guardar Pedido"):
                    if numero:
                        insert_data("pedidos", {
                            "numero": numero,
                            "cliente_id": cliente_opciones[cliente_nombre],
                            "fecha_entrega": str(fecha_entrega),
                            "cantidad": cantidad,
                            "producto_sku": producto_sku,
                            "lleva_rt": 1 if lleva_rt else 0
                        })
                        st.rerun()
                    else:
                        st.error("El número de pedido es obligatorio")

# ============================================
# PLANIFICACIÓN
# ============================================
elif menu == "🏭 Planificación":
    st.header("🏭 Planificación de Producción")
    
    st.info("🚧 En desarrollo... Próximamente: algoritmo de asignación de pedidos a máquinas")
    
    # Aquí implementaremos el algoritmo de planificación
    maquinas = get_data("maquinas")
    pedidos = get_data("pedidos")
    
    if maquinas and pedidos:
        st.subheader("📊 Resumen para planificación")
        st.write(f"**Máquinas disponibles:** {len(maquinas)}")
        st.write(f"**Pedidos pendientes:** {len(pedidos)}")
        
        # Mostrar tabla de pedidos pendientes
        df_pedidos = pd.DataFrame(pedidos)
        if not df_pedidos.empty:
            st.dataframe(df_pedidos[['numero', 'cantidad', 'fecha_entrega', 'producto_sku']], use_container_width=True)
    else:
        st.warning("Faltan máquinas o pedidos para iniciar la planificación")
