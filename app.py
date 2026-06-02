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
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im51YnhodGxlcnR1d21ldnh6dXlkIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODAzMTI4ODYsImV4cCI6MjA5NTg4ODg4Nn0.sxXfypXZHyqFnXL1xeXdvXw925C6v-dg9Kg--7KNLWs"

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
        else:
            return []
    except Exception as e:
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
        return None

# Verificar conexion
with st.spinner("Conectando a base de datos..."):
    test = get_data("maquinas")

if test is not None:
    st.sidebar.success("Conectado a Supabase")
else:
    st.sidebar.error("Error de conexion")

# Menu
menu = st.sidebar.radio(
    "MENU",
    ["Dashboard", "Maquinas", "Clientes", "Productos", "Pedidos", "IA Planificar"]
)

if menu == "Dashboard":
    st.header("Dashboard")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Maquinas", len(get_data("maquinas")))
    col2.metric("Clientes", len(get_data("clientes")))
    col3.metric("Productos", len(get_data("productos")))
    col4.metric("Pedidos", len(get_data("pedidos")))

elif menu == "Maquinas":
    st.header("Maquinas")
    tab1, tab2 = st.tabs(["Listado", "Nueva"])
    with tab1:
        for m in get_data("maquinas"):
            st.write(f"{m.get('nombre')} - {m.get('velocidad')} latas/min")
    with tab2:
        with st.form("new_maquina"):
            nombre = st.text_input("Nombre")
            velocidad = st.number_input("Velocidad", min_value=1, value=100)
            capacidad = st.number_input("Capacidad", min_value=1, value=30000)
            formato = st.text_input("Formato")
            if st.form_submit_button("Guardar"):
                insert_data("maquinas", {
                    "nombre": nombre,
                    "velocidad": velocidad,
                    "capacidad": capacidad,
                    "formato": formato
                })
                st.rerun()

elif menu == "Clientes":
    st.header("Clientes")
    tab1, tab2 = st.tabs(["Listado", "Nuevo"])
    with tab1:
        for c in get_data("clientes"):
            st.write(f"{c.get('nombre')} - Prioridad: {c.get('prioridad')}")
    with tab2:
        with st.form("new_cliente"):
            nombre = st.text_input("Nombre")
            prioridad = st.slider("Prioridad (1-10)", 1, 10, 5)
            penalizacion = st.number_input("Penalizacion", min_value=0, value=0)
            if st.form_submit_button("Guardar"):
                insert_data("clientes", {
                    "nombre": nombre,
                    "prioridad": prioridad,
                    "penalizacion": penalizacion
                })
                st.rerun()

elif menu == "Productos":
    st.header("Productos")
    tab1, tab2 = st.tabs(["Listado", "Nuevo"])
    with tab1:
        for p in get_data("productos"):
            st.write(f"{p.get('sku')} - {p.get('nombre')}")
    with tab2:
        with st.form("new_producto"):
            sku = st.text_input("SKU")
            nombre = st.text_input("Nombre")
            formato = st.selectbox("Formato", ["RR-120", "RR-90", "RO-85", "RT"])
            familia = st.text_input("Familia")
            if st.form_submit_button("Guardar"):
                insert_data("productos", {
                    "sku": sku,
                    "nombre": nombre,
                    "formato": formato,
                    "familia": familia
                })
                st.rerun()

elif menu == "Pedidos":
    st.header("Pedidos")
    clientes = get_data("clientes")
    productos = get_data("productos")
    if not clientes or not productos:
        st.warning("Primero crea clientes y productos")
    else:
        tab1, tab2 = st.tabs(["Listado", "Nuevo"])
        with tab1:
            for p in get_data("pedidos"):
                st.write(f"{p.get('numero')} - {p.get('cantidad')} latas")
        with tab2:
            with st.form("new_pedido"):
                col1, col2 = st.columns(2)
                with col1:
                    numero = st.text_input("Numero")
                    cliente_dict = {c['nombre']: c['id'] for c in clientes}
                    cliente = st.selectbox("Cliente", list(cliente_dict.keys()))
                with col2:
                    fecha = st.date_input("Fecha entrega", datetime.now())
                    producto_dict = {p['sku']: p['nombre'] for p in productos}
                    producto = st.selectbox("Producto", list(producto_dict.keys()))
                    cantidad = st.number_input("Cantidad", min_value=1, value=10000)
                    lleva_rt = st.checkbox("Lleva RT")
                if st.form_submit_button("Guardar"):
                    insert_data("pedidos", {
                        "numero": numero,
                        "cliente_id": cliente_dict[cliente],
                        "fecha_entrega": str(fecha),
                        "cantidad": cantidad,
                        "producto_sku": producto,
                        "lleva_rt": 1 if lleva_rt else 0
                    })
                    st.rerun()

elif menu == "IA Planificar":
    st.header("Planificacion con IA")
    maquinas = get_data("maquinas")
    pedidos = get_data("pedidos")
    clientes = get_data("clientes")
    productos = get_data("productos")
    col1, col2 = st.columns(2)
    col1.info(f"Maquinas: {len(maquinas)}")
    col2.info(f"Pedidos: {len(pedidos)}")
    if not maquinas:
        st.error("No hay maquinas")
    elif not pedidos:
        st.warning("No hay pedidos")
    else:
        if st.button("Ejecutar IA"):
            resultado = planificar_con_ia(maquinas, pedidos, clientes, productos)
            if resultado:
                st.success("Planificacion completada")
                if 'analisis' in resultado:
                    st.info(resultado['analisis'])
                if 'asignaciones' in resultado:
                    st.dataframe(pd.DataFrame(resultado['asignaciones']))
            else:
                st.error("Error en la IA")
