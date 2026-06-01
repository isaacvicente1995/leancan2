import streamlit as st
import requests
import pandas as pd
from datetime import datetime
import json
from openai import OpenAI

st.set_page_config(page_title="LeanCan", page_icon="🥫", layout="wide")

st.title("🥫 LeanCan Scheduler - IA con DeepSeek")

# Configuración de Supabase
SUPABASE_URL = "https://nubxhtlertuwmevxzuyd.supabase.co/rest/v1"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im51YnhodGxlcnR1d21ldnh6dXlkIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODAzMTI4ODYsImV4cCI6MjA5NTg4ODg4Nn0.sxXfypXZHyqFnXL1xeXdvXw925C6v-dg9Kg--7KNLWs"

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

def get_data(table):
    response = requests.get(f"{SUPABASE_URL}/{table}", headers=HEADERS)
    if response.status_code == 200:
        return response.json()
    return []

def insert_data(table, data):
    response = requests.post(f"{SUPABASE_URL}/{table}", headers=HEADERS, json=data)
    return response.status_code in [200, 201]

def delete_data(table, id_field, id_value):
    response = requests.delete(f"{SUPABASE_URL}/{table}?{id_field}=eq.{id_value}", headers=HEADERS)
    return response.status_code == 204

# ============================================
# IA REAL CON DEEPSEEK (GRATUITA)
# ============================================
def planificar_con_ia(maquinas, pedidos, clientes, productos):
    if not maquinas or not pedidos:
        return None
    
    contexto = f"""
Eres un planificador experto de producción en una fabrica de conservas.

## MAQUINAS DISPONIBLES:
{json.dumps(maquinas, indent=2, ensure_ascii=False)}

## CLIENTES Y PRIORIDADES:
{json.dumps(clientes, indent=2, ensure_ascii=False)}

## PRODUCTOS:
{json.dumps(productos, indent=2, ensure_ascii=False)}

## PEDIDOS PENDIENTES:
{json.dumps(pedidos, indent=2, ensure_ascii=False)}

## REGLAS DE NEGOCIO:
1. Cada pedido debe asignarse a UNA maquina
2. No se puede exceder la capacidad diaria de cada maquina
3. Los pedidos con RT (lleva_rt = true) SOLO pueden ir a la maquina E5
4. Los pedidos pequenos (<20000 latas) pueden ir a cualquier maquina
5. Priorizar pedidos con clientes de mayor prioridad y fechas mas cercanas

## INSTRUCCIONES:
Devuelve SOLO un JSON valido con este formato exacto:

{
    "asignaciones": [
        {
            "pedido_id": 1,
            "pedido_numero": "P001",
            "maquina_asignada": "E1",
            "cantidad_asignada": 50000,
            "justificacion": "texto explicativo"
        }
    ],
    "saturacion": {
        "E1": 45,
        "E2": 0,
        "E3": 0,
        "E5": 30,
        "E8": 0
    },
    "analisis_general": "Resumen del razonamiento"
}
"""
    
    try:
        client = OpenAI(
            api_key=st.secrets["DEEPSEEK_API_KEY"],
            base_url="https://api.deepseek.com"
        )
        
        with st.spinner("DeepSeek IA esta analizando los pedidos..."):
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": "Eres un experto planificador. Responde SOLO con JSON valido."},
                    {"role": "user", "content": contexto}
                ],
                temperature=0.3
            )
        
        respuesta_texto = response.choices[0].message.content
        
        if respuesta_texto.startswith("```json"):
            respuesta_texto = respuesta_texto[7:]
        if respuesta_texto.endswith("```"):
            respuesta_texto = respuesta_texto[:-3]
        
        resultado = json.loads(respuesta_texto.strip())
        return resultado
        
    except Exception as e:
        st.error(f"Error: {e}")
        return None

# ============================================
# MENU PRINCIPAL
# ============================================
menu = st.sidebar.radio(
    "MENU PRINCIPAL",
    ["Dashboard", "Maquinas", "Clientes", "Productos", "Pedidos", "IA DeepSeek - Planificar"]
)

# ============================================
# DASHBOARD
# ============================================
if menu == "Dashboard":
    st.header("Dashboard")
    
    col1, col2, col3, col4 = st.columns(4)
    
    maquinas = get_data("maquinas")
    col1.metric("Maquinas", len(maquinas))
    
    clientes = get_data("clientes")
    col2.metric("Clientes", len(clientes))
    
    productos = get_data("productos")
    col3.metric("Productos", len(productos))
    
    pedidos = get_data("pedidos")
    col4.metric("Pedidos", len(pedidos))
    
    st.markdown("---")
    
    st.subheader("Estado de Maquinas")
    if maquinas:
        df_maq = pd.DataFrame(maquinas)
        st.dataframe(df_maq[['nombre', 'velocidad', 'capacidad', 'formato']], use_container_width=True)
    else:
        st.info("No hay maquinas registradas")

# ============================================
# MAQUINAS
# ============================================
elif menu == "Maquinas":
    st.header("Gestion de Maquinas")
    
    tab1, tab2 = st.tabs(["Listado", "Anadir Maquina"])
    
    with tab1:
        maquinas = get_data("maquinas")
        if maquinas:
            for m in maquinas:
                with st.expander(f" {m.get('nombre', 'Sin nombre')}"):
                    col1, col2, col3, col4 = st.columns([2,2,2,1])
                    col1.metric("Velocidad", f"{m.get('velocidad', 0)} latas/min")
                    col2.metric("Capacidad", f"{m.get('capacidad', 0):,} latas/dia")
                    col3.metric("Formato", m.get('formato', 'N/A'))
                    if col4.button("Eliminar", key=f"del_maq_{m.get('id')}"):
                        delete_data("maquinas", "id", m.get('id'))
                        st.rerun()
        else:
            st.info("No hay maquinas registradas")
    
    with tab2:
        with st.form("form_maquina"):
            col1, col2 = st.columns(2)
            with col1:
                nombre = st.text_input("Nombre (E1, E2, E3, E5, E8)")
                velocidad = st.number_input("Velocidad (latas/min)", min_value=1, value=100)
            with col2:
                formato = st.text_input("Formatos compatibles")
                capacidad = st.number_input("Capacidad diaria (latas)", min_value=1, value=30000)
            
            if st.form_submit_button("Guardar Maquina"):
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
elif menu == "Clientes":
    st.header("Gestion de Clientes")
    
    tab1, tab2 = st.tabs(["Listado", "Anadir Cliente"])
    
    with tab1:
        clientes = get_data("clientes")
        if clientes:
            for c in clientes:
                with st.expander(f" {c.get('nombre', 'Sin nombre')}"):
                    col1, col2, col3 = st.columns([2,2,1])
                    col1.metric("Prioridad", f"{c.get('prioridad', 5)}/10")
                    col2.metric("Penalizacion", f"{c.get('penalizacion', 0)} €/dia")
                    if col3.button("Eliminar", key=f"del_cli_{c.get('id')}"):
                        delete_data("clientes", "id", c.get('id'))
                        st.rerun()
        else:
            st.info("No hay clientes registrados")
    
    with tab2:
        with st.form("form_cliente"):
            nombre = st.text_input("Nombre del cliente")
            col1, col2 = st.columns(2)
            with col1:
                prioridad = st.slider("Prioridad (1-10)", 1, 10, 5)
            with col2:
                penalizacion = st.number_input("Penalizacion (€/dia retraso)", min_value=0, value=0)
            
            if st.form_submit_button("Guardar Cliente"):
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
elif menu == "Productos":
    st.header("Gestion de Productos")
    
    tab1, tab2 = st.tabs(["Listado", "Anadir Producto"])
    
    with tab1:
        productos = get_data("productos")
        if productos:
            for p in productos:
                with st.expander(f" {p.get('sku', 'Sin SKU')} - {p.get('nombre', 'Sin nombre')}"):
                    col1, col2, col3, col4 = st.columns([1,1,1,1])
                    col1.metric("SKU", p.get('sku', 'N/A'))
                    col2.metric("Formato", p.get('formato', 'N/A'))
                    col3.metric("Familia", p.get('familia', '-'))
                    if col4.button("Eliminar", key=f"del_prod_{p.get('sku')}"):
                        delete_data("productos", "sku", p.get('sku'))
                        st.rerun()
        else:
            st.info("No hay productos registrados")
    
    with tab2:
        with st.form("form_producto"):
            col1, col2 = st.columns(2)
            with col1:
                sku = st.text_input("SKU (codigo unico)")
                nombre = st.text_input("Nombre del producto")
            with col2:
                formato = st.selectbox("Formato de lata", ["RR-120", "RR-90", "RO-85", "RT"])
                familia = st.text_input("Familia")
            
            if st.form_submit_button("Guardar Producto"):
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
elif menu == "Pedidos":
    st.header("Gestion de Pedidos")
    
    clientes = get_data("clientes")
    productos = get_data("productos")
    
    if not clientes:
        st.warning("Primero crea clientes")
    elif not productos:
        st.warning("Primero crea productos")
    else:
        tab1, tab2 = st.tabs(["Listado", "Nuevo Pedido"])
        
        with tab1:
            pedidos = get_data("pedidos")
            if pedidos:
                clientes_dict = {c.get('id'): c.get('nombre') for c in clientes}
                for ped in pedidos:
                    cliente_nombre = clientes_dict.get(ped.get('cliente_id'), "Desconocido")
                    with st.expander(f"Pedido {ped.get('numero', 'Sin numero')} - {cliente_nombre}"):
                        col1, col2, col3, col4 = st.columns(4)
                        col1.metric("Fecha entrega", ped.get('fecha_entrega', 'N/A'))
                        col2.metric("Cantidad", f"{ped.get('cantidad', 0):,} latas")
                        col3.metric("Producto", ped.get('producto_sku', 'N/A'))
                        col4.metric("Lleva RT", "Si" if ped.get('lleva_rt') else "No")
                        if st.button("Eliminar", key=f"del_ped_{ped.get('id')}"):
                            delete_data("pedidos", "id", ped.get('id'))
                            st.rerun()
            else:
                st.info("No hay pedidos registrados")
        
        with tab2:
            with st.form("form_pedido"):
                col1, col2 = st.columns(2)
                with col1:
                    numero = st.text_input("Numero de pedido")
                    cliente_opciones = {c.get('nombre'): c.get('id') for c in clientes}
                    cliente_nombre = st.selectbox("Cliente", list(cliente_opciones.keys()))
                with col2:
                    fecha_entrega = st.date_input("Fecha de entrega", datetime.now())
                    producto_opciones = {p.get('sku'): p.get('nombre') for p in productos}
                    producto_sku = st.selectbox("Producto", list(producto_opciones.keys()))
                    cantidad = st.number_input("Cantidad (latas)", min_value=1, value=10000, step=1000)
                    lleva_rt = st.checkbox("Lleva retractil (RT)")
                
                if st.form_submit_button("Guardar Pedido"):
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
                        st.error("El numero de pedido es obligatorio")

# ============================================
# PLANIFICACION CON DEEPSEEK IA
# ============================================
elif menu == "IA DeepSeek - Planificar":
    st.header("Planificacion con DeepSeek IA (Gratuita)")
    
    maquinas = get_data("maquinas")
    pedidos = get_data("pedidos")
    clientes = get_data("clientes")
    productos = get_data("productos")
    
    col1, col2 = st.columns(2)
    with col1:
        st.info(f"Maquinas: {len(maquinas)}")
        st.info(f"Clientes: {len(clientes)}")
    with col2:
        st.info(f"Productos: {len(productos)}")
        st.info(f"Pedidos: {len(pedidos)}")
    
    if not maquinas:
        st.error("No hay maquinas registradas. Ve a 'Maquinas' para anadir.")
    elif not pedidos:
        st.warning("No hay pedidos para planificar. Crea algunos pedidos primero.")
    else:
        if st.button("Ejecutar DeepSeek IA", type="primary"):
            resultado = planificar_con_ia(maquinas, pedidos, clientes, productos)
            
            if resultado:
                st.success("Planificacion completada por DeepSeek IA")
                
                st.subheader("Analisis de la IA")
                st.info(resultado.get('analisis_general', 'No se proporciono analisis'))
                
                st.subheader("Saturacion de Maquinas")
                saturacion = resultado.get('saturacion', {})
                if saturacion:
                    df_sat = pd.DataFrame(list(saturacion.items()), columns=['Maquina', 'Saturacion %'])
                    st.bar_chart(df_sat.set_index('Maquina'))
                    
                    for maq, sat in saturacion.items():
                        if sat > 85:
                            st.warning(f"{maq} esta al {sat}% de capacidad - Riesgo de sobrecarga")
                        elif sat > 70:
                            st.info(f"{maq} esta al {sat}% de capacidad")
                
                st.subheader("Asignaciones de la IA")
                asignaciones = resultado.get('asignaciones', [])
                if asignaciones:
                    df_asig = pd.DataFrame(asignaciones)
                    st.dataframe(df_asig, use_container_width=True)
                    
                    with st.expander("Ver justificaciones detalladas"):
                        for a in asignaciones:
                            st.write(f"**{a.get('pedido_numero')}** -> {a.get('maquina_asignada')}")
                            st.caption(f"{a.get('justificacion', 'Sin justificacion')}")
                            st.markdown("---")
            else:
                st.error("La IA no pudo generar una planificacion")
