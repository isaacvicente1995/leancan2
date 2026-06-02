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
SUPABASE_KEY = st.secrets["eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im51YnhodGxlcnR1d21ldnh6dXlkIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc4MDMxMjg4NiwiZXhwIjoyMDk1ODg4ODg2fQ.pFNHfgUB7Nxz5i3ZDBQtwbC95wvxjs77SwmE_5ROZzw"]

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

def delete_data(table, id_field, id_value):
    try:
        response = requests.delete(f"{SUPABASE_URL}/{table}?{id_field}=eq.{id_value}", headers=HEADERS)
        return response.status_code == 204
    except:
        return False

# ============================================
# FUNCIÓN PARA PARSEAR PEDIDO DESDE TEXTO
# ============================================
def parsear_pedido(texto):
    """
    Parsea el texto de un pedido y extrae las líneas
    """
    lineas = []
    
    # Buscar patrones: cantidad + SKU + descripción
    patron = r'(\d{6,})\s+([A-Z0-9\-]+)\s+([A-Z\s]+)\s+([\d\.]+)\s+(\d+)\s+(\d+)'
    
    lineas_raw = texto.split('\n')
    
    for linea in lineas_raw:
        # Buscar SKU (código de 6 dígitos)
        sku_match = re.search(r'(\d{6,})\s+([A-Z0-9\-]+)', linea)
        if sku_match:
            sku = sku_match.group(1)
            
            # Buscar cantidad
            cant_match = re.search(r'(\d{1,3}(?:\.\d{3})*)\s+latas?', linea.lower())
            if not cant_match:
                cant_match = re.search(r'(\d{1,3}(?:\.\d{3})*)\s+$', linea)
            
            cantidad = 0
            if cant_match:
                cantidad_str = cant_match.group(1).replace('.', '')
                cantidad = int(cantidad_str) if cantidad_str.isdigit() else 0
            
            # Determinar si lleva RT
            lleva_rt = 'RT10' in linea or 'retractil' in linea.lower()
            tipo_rt = 'RT10' if lleva_rt else None
            
            # Extraer nombre del producto
            nombre = linea[linea.find(sku)+len(sku):].strip()
            if len(nombre) > 50:
                nombre = nombre[:50]
            
            if cantidad > 0:
                lineas.append({
                    'sku': sku,
                    'nombre': nombre,
                    'cantidad': cantidad,
                    'lleva_rt': lleva_rt,
                    'tipo_rt': tipo_rt
                })
    
    return lineas

# ============================================
# FUNCIÓN IA CON DEEPSEEK
# ============================================
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
# FUNCIÓN PARA SEPARAR LÍNEAS DE TRABAJO
# ============================================
def separar_lineas_trabajo(pedido_lines):
    """
    Separa las líneas del pedido en líneas de trabajo por máquina
    """
    lineas_trabajo = {
        "E1": [],  # Rápida RR-120
        "E2": [],  # Versátil
        "E3": [],  # Rápida RR-120
        "E5": [],  # RT
        "E8": []   # RO-85
    }
    
    for linea in pedido_lines:
        if linea.get('lleva_rt'):
            lineas_trabajo["E5"].append(linea)
        else:
            # Por formato (simplificado, se mejorará con datos reales)
            if "RR-120" in linea.get('sku', ''):
                # Alternar entre E1 y E3 para balancear
                if len(lineas_trabajo["E1"]) <= len(lineas_trabajo["E3"]):
                    lineas_trabajo["E1"].append(linea)
                else:
                    lineas_trabajo["E3"].append(linea)
            else:
                lineas_trabajo["E2"].append(linea)
    
    return lineas_trabajo

# ============================================
# CARGAR DATOS INICIALES
# ============================================
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
# CARGAR PEDIDO
# ============================================
elif menu == "📄 Cargar Pedido":
    st.header("📄 Cargar Pedido desde Archivo")
    
    # Opción 1: Pegar texto
    st.subheader("Opción 1: Pegar el texto del pedido")
    texto_pedido = st.text_area("Pega aquí el contenido del pedido", height=200)
    
    if texto_pedido:
        lineas = parsear_pedido(texto_pedido)
        if lineas:
            st.success(f"✅ Se encontraron {len(lineas)} líneas")
            st.dataframe(pd.DataFrame(lineas), use_container_width=True)
            
            # Separar en líneas de trabajo
            st.subheader("📋 Líneas de Trabajo por Máquina")
            lineas_trabajo = separar_lineas_trabajo(lineas)
            
            for maquina, asignaciones in lineas_trabajo.items():
                if asignaciones:
                    total = sum(a['cantidad'] for a in asignaciones)
                    with st.expander(f"🖥️ {maquina} - {total:,} latas"):
                        st.dataframe(pd.DataFrame(asignaciones), use_container_width=True)
    
    # Opción 2: Subir archivo
    st.subheader("Opción 2: Subir archivo (CSV o Excel)")
    archivo = st.file_uploader("Selecciona un archivo", type=['csv', 'xlsx', 'txt'])
    
    if archivo:
        if archivo.name.endswith('.csv'):
            df = pd.read_csv(archivo)
        elif archivo.name.endswith('.xlsx'):
            df = pd.read_excel(archivo)
        else:
            # Archivo de texto
            contenido = archivo.read().decode('utf-8')
            lineas = parsear_pedido(contenido)
            df = pd.DataFrame(lineas)
        
        st.dataframe(df, use_container_width=True)
        
        # Convertir a líneas de pedido
        pedido_numero = st.text_input("Número de pedido", "RAF2026/206")
        cliente = st.selectbox("Cliente", [c['nombre'] for c in clientes_data] if clientes_data else ["RAMIREZ Y CIA"])
        
        if st.button("💾 Guardar Pedido en Base de Datos"):
            # Obtener cliente_id
            cliente_id = None
            for c in clientes_data:
                if c['nombre'] == cliente:
                    cliente_id = c['id']
                    break
            
            if not cliente_id:
                cliente_id = 1
            
            # Guardar cada línea
            for _, row in df.iterrows():
                insert_data("pedidos", {
                    "numero": pedido_numero,
                    "cliente_id": cliente_id,
                    "fecha_entrega": str(datetime.now().date()),
                    "cantidad": int(row.get('cantidad', 0)),
                    "producto_sku": row.get('sku', ''),
                    "lleva_rt": 1 if row.get('lleva_rt', False) else 0
                })
            
            st.success(f"✅ Pedido {pedido_numero} guardado con {len(df)} líneas")
            
            # Mostrar separación de líneas de trabajo
            st.subheader("📋 Propuesta de Separación en Líneas de Trabajo")
            lineas_trabajo = separar_lineas_trabajo(df.to_dict('records'))
            
            for maquina, asignaciones in lineas_trabajo.items():
                if asignaciones:
                    total = sum(a['cantidad'] for a in asignaciones)
                    st.write(f"**{maquina}**: {total:,} latas")
                    for a in asignaciones:
                        rt = " (con RT)" if a.get('lleva_rt') else ""
                        st.write(f"  - {a['sku']}: {a['cantidad']:,} latas{rt}")

# ============================================
# MÁQUINAS (simplificado)
# ============================================
elif menu == "⚙️ Máquinas":
    st.header("⚙️ Máquinas")
    for m in maquinas_data:
        st.write(f"🖥️ {m.get('nombre')}: {m.get('velocidad')} latas/min, Cap: {m.get('capacidad'):,} latas/día")

# ============================================
# CLIENTES (simplificado)
# ============================================
elif menu == "👥 Clientes":
    st.header("👥 Clientes")
    for c in clientes_data:
        st.write(f"🏢 {c.get('nombre')}: Prioridad {c.get('prioridad')}/10")

# ============================================
# PRODUCTOS (simplificado)
# ============================================
elif menu == "📦 Productos":
    st.header("📦 Productos")
    for p in productos_data:
        st.write(f"📦 {p.get('sku')}: {p.get('nombre')}")

# ============================================
# PEDIDOS (simplificado)
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
            resultado = planificar_con_ia(maquinas_data, pedidos_data, clientes_data, productos_data)
            if resultado:
                st.success("✅ Planificación completada")
                if 'analisis' in resultado:
                    st.info(f"🧠 {resultado['analisis']}")
                if 'asignaciones' in resultado:
                    st.dataframe(pd.DataFrame(resultado['asignaciones']))
                if 'saturacion' in resultado:
                    st.bar_chart(pd.DataFrame(list(resultado['saturacion'].items()), columns=['Máquina', '%']).set_index('Máquina'))
