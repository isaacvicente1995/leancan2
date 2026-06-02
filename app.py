import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
import re
import plotly.express as px
import plotly.graph_objects as go
import time

st.set_page_config(
    page_title="LeanCan - Planificación Industrial",
    page_icon="🏭",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS PERSONALIZADO
st.markdown("""
<style>
    .stApp { background-color: #f0f2f6; }
    h1 { color: #1a365d !important; border-bottom: 3px solid #2c5282 !important; padding-bottom: 15px !important; }
    .metric-card { background: linear-gradient(135deg, #1e3a5f 0%, #2c5282 100%); border-radius: 12px; padding: 20px; color: white; }
    .machine-card { background: white; border-radius: 10px; padding: 15px; margin: 10px 0; border-left: 4px solid; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
    .machine-name { font-size: 20px; font-weight: bold; }
    .stButton > button { background-color: #2c5282; color: white; font-weight: 600; border-radius: 8px; }
    .plan-table { font-size: 12px; }
    .plan-table th { background-color: #2c5282; color: white; }
</style>
""", unsafe_allow_html=True)

# CONFIGURACIÓN SUPABASE
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

def extraer_lineas(texto):
    lineas = []
    patron_sku = r'\b(\d{13}|\d{10})\b'
    patron_cantidad = r'\b(\d{1,3}(?:\.\d{3})*|\d{4,})\b'
    
    for linea in texto.split('\n'):
        if not linea.strip():
            continue
        sku_match = re.search(patron_sku, linea)
        cantidades = re.findall(patron_cantidad, linea)
        cantidad = 0
        for c in cantidades:
            try:
                num = int(c.replace('.', ''))
                if 1000 < num < 1000000:
                    cantidad = num
                    break
            except:
                continue
        lleva_rt = 'RT10' in linea or 'RT' in linea.upper()
        if sku_match and cantidad > 0:
            lineas.append({'sku': sku_match.group(1), 'cantidad': cantidad, 'lleva_rt': lleva_rt})
    return lineas

def calcular_carga_real(pedidos, clientes_dict):
    capacidades = {'E1': 54000, 'E2': 32400, 'E3': 54000, 'E5': 33750, 'E8': 48600}
    carga = {'E1': 0, 'E2': 0, 'E3': 0, 'E5': 0, 'E8': 0}
    
    for pedido in pedidos:
        cantidad = pedido.get('cantidad', 0)
        lleva_rt = pedido.get('lleva_rt', False)
        if lleva_rt:
            carga['E5'] += cantidad
        else:
            # Distribuir entre E1, E2, E3 según carga
            min_maq = min(carga, key=lambda x: carga[x] if x in ['E1', 'E2', 'E3'] else float('inf'))
            if min_maq in ['E1', 'E2', 'E3']:
                carga[min_maq] += cantidad
    
    porcentajes = {}
    for maq in capacidades:
        porcentajes[maq] = round((carga[maq] / capacidades[maq]) * 100, 1) if capacidades[maq] > 0 else 0
    return carga, porcentajes

def generar_planificacion_detallada(pedidos, fecha_inicio, dias=7):
    """
    Genera planificación detallada: qué produce cada máquina cada día
    """
    capacidades = {'E1': 54000, 'E2': 32400, 'E3': 54000, 'E5': 33750, 'E8': 48600}
    
    # Inicializar planificación
    plan = {}
    for maq in ['E1', 'E2', 'E3', 'E5', 'E8']:
        plan[maq] = {}
        for i in range(dias):
            plan[maq][i] = []
    
    carga_diaria = {maq: {i: 0 for i in range(dias)} for maq in ['E1', 'E2', 'E3', 'E5', 'E8']}
    
    # Ordenar pedidos por fecha de entrega (más urgente primero)
    pedidos_ordenados = sorted(pedidos, key=lambda x: (x.get('fecha_entrega', '9999-12-31'), -x.get('cantidad', 0)))
    
    for pedido in pedidos_ordenados:
        cantidad = pedido.get('cantidad', 0)
        lleva_rt = pedido.get('lleva_rt', False)
        pedido_numero = pedido.get('numero', 'N/A')
        cliente_nombre = pedido.get('cliente_nombre', 'N/A')
        producto = pedido.get('producto_sku', 'N/A')
        
        # Determinar máquinas posibles
        if lleva_rt:
            maquinas_posibles = ['E5']
        else:
            maquinas_posibles = ['E1', 'E2', 'E3']
        
        cantidad_restante = cantidad
        
        for maq in maquinas_posibles:
            for dia in range(dias):
                disponible = capacidades[maq] - carga_diaria[maq][dia]
                if disponible <= 0:
                    continue
                
                asignar = min(cantidad_restante, disponible)
                if asignar > 0:
                    plan[maq][dia].append({
                        'pedido': pedido_numero,
                        'cliente': cliente_nombre,
                        'producto': producto,
                        'cantidad': asignar,
                        'fecha_entrega': pedido.get('fecha_entrega', 'N/A'),
                        'rt': lleva_rt
                    })
                    carga_diaria[maq][dia] += asignar
                    cantidad_restante -= asignar
                    
                    if cantidad_restante <= 0:
                        break
            if cantidad_restante <= 0:
                break
    
    # Calcular saturación
    saturacion = {}
    for maq in ['E1', 'E2', 'E3', 'E5', 'E8']:
        total_semana = sum(carga_diaria[maq][dia] for dia in range(dias))
        saturacion[maq] = round((total_semana / (capacidades[maq] * dias)) * 100, 1) if capacidades[maq] > 0 else 0
    
    return plan, saturacion, carga_diaria

# CARGA DE DATOS
with st.spinner("🔄 Cargando datos..."):
    maquinas = get_data("maquinas")
    clientes = get_data("clientes")
    productos = get_data("productos")
    pedidos = get_data("pedidos")
    clientes_dict = {c['id']: c['nombre'] for c in clientes}
    for p in pedidos:
        p['cliente_nombre'] = clientes_dict.get(p.get('cliente_id', 0), 'Desconocido')

carga_real, porcentaje_carga = calcular_carga_real(pedidos, clientes_dict)

# MENÚ
st.sidebar.markdown("<h2 style='text-align: center; color: white;'>🏭 LeanCan</h2>", unsafe_allow_html=True)
menu = st.sidebar.radio("", ["📊 PANEL DE CONTROL", "🏭 LÍNEAS DE PRODUCCIÓN", "📅 PLANIFICACIÓN", "📦 PEDIDOS", "📄 IMPORTAR PEDIDO"])

# ============================================
# PANEL DE CONTROL
# ============================================
if menu == "📊 PANEL DE CONTROL":
    st.markdown("<h1>📊 Panel de Control Industrial</h1>", unsafe_allow_html=True)
    col1, col2, col3, col4 = st.columns(4)
    total_pedidos = len(pedidos)
    total_latas = sum(p.get('cantidad', 0) for p in pedidos)
    pedidos_rt = sum(1 for p in pedidos if p.get('lleva_rt', False))
    
    with col1: st.markdown(f"<div class='metric-card'><h3>📦 PEDIDOS</h3><div class='value'>{total_pedidos}</div></div>", unsafe_allow_html=True)
    with col2: st.markdown(f"<div class='metric-card'><h3>🥫 TOTAL LATAS</h3><div class='value'>{total_latas:,.0f}</div></div>", unsafe_allow_html=True)
    with col3: st.markdown(f"<div class='metric-card'><h3>📦 CON RT</h3><div class='value'>{pedidos_rt}</div></div>", unsafe_allow_html=True)
    with col4: st.markdown(f"<div class='metric-card'><h3>🏭 MÁQUINAS</h3><div class='value'>5</div></div>", unsafe_allow_html=True)
    
    if pedidos:
        st.markdown("---")
        st.subheader("📋 Lista de Pedidos")
        df_ped = pd.DataFrame(pedidos)
        st.dataframe(df_ped[['numero', 'cliente_nombre', 'cantidad', 'fecha_entrega', 'lleva_rt']], use_container_width=True)

# ============================================
# LÍNEAS DE PRODUCCIÓN
# ============================================
elif menu == "🏭 LÍNEAS DE PRODUCCIÓN":
    st.markdown("<h1>🏭 Líneas de Producción</h1>", unsafe_allow_html=True)
    
    maquinas_info = {
        'E1': {'formato': 'RR-120', 'velocidad': 200, 'capacidad': 54000, 'desc': 'Línea rápida RR-120'},
        'E2': {'formato': 'RR-120/RR-90', 'velocidad': 120, 'capacidad': 32400, 'desc': 'Línea versátil'},
        'E3': {'formato': 'RR-120', 'velocidad': 200, 'capacidad': 54000, 'desc': 'Línea rápida RR-120'},
        'E5': {'formato': 'RT', 'velocidad': 125, 'capacidad': 33750, 'desc': 'Retráctil'},
        'E8': {'formato': 'RO-85', 'velocidad': 180, 'capacidad': 48600, 'desc': 'Línea especial RO-85'}
    }
    
    for maq in ['E1', 'E2', 'E3', 'E5', 'E8']:
        info = maquinas_info[maq]
        carga_actual = porcentaje_carga.get(maq, 0)
        color_border = "#2c5282" if carga_actual < 70 else "#ed8936" if carga_actual < 90 else "#e53e3e"
        
        st.markdown(f"""
        <div class="machine-card" style="border-left-color: {color_border};">
            <div style="display: flex; justify-content: space-between;">
                <span class="machine-name">{maq}</span>
                <span style="font-size: 12px;">{info['desc']}</span>
            </div>
            <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 15px; margin-top: 10px;">
                <div><div style="font-size: 11px; color: #718096;">VELOCIDAD</div><div style="font-size: 18px; font-weight: bold;">{info['velocidad']} <span style="font-size: 12px;">latas/min</span></div></div>
                <div><div style="font-size: 11px; color: #718096;">CAPACIDAD DÍA</div><div style="font-size: 18px; font-weight: bold;">{info['capacidad']:,} <span style="font-size: 12px;">latas</span></div></div>
                <div><div style="font-size: 11px; color: #718096;">CARGA ACTUAL</div><div style="font-size: 18px; font-weight: bold;">{carga_actual}%</div><progress value="{carga_actual}" max="100" style="width: 100%; height: 8px; border-radius: 4px;"></progress></div>
            </div>
        </div>
        """, unsafe_allow_html=True)

# ============================================
# PLANIFICACIÓN DETALLADA
# ============================================
elif menu == "📅 PLANIFICACIÓN":
    st.markdown("<h1>📅 Planificación de Producción</h1>", unsafe_allow_html=True)
    
    if not pedidos:
        st.warning("⚠️ No hay pedidos para planificar. Importa pedidos primero.")
    else:
        col1, col2 = st.columns([2, 1])
        with col1:
            fecha_inicio = st.date_input("Fecha de inicio", datetime.now())
        with col2:
            dias = st.selectbox("Horizonte (días)", [5, 7, 10, 14], index=1)
        
        if st.button("🚀 GENERAR PLANIFICACIÓN", type="primary", use_container_width=True):
            with st.spinner("Generando planificación detallada..."):
                plan, saturacion, cargas = generar_planificacion_detallada(pedidos, fecha_inicio, dias)
            
            # Gráfico de saturación
            st.subheader("📊 Saturación de Líneas")
            df_sat = pd.DataFrame([{"Línea": k, "Saturación": v} for k, v in saturacion.items()])
            fig = px.bar(df_sat, x="Línea", y="Saturación", text="Saturación", 
                        color="Saturación", color_continuous_scale=["#2ecc71", "#f39c12", "#e74c3c"])
            fig.update_traces(textposition='outside')
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True)
            
            st.markdown("---")
            
            # Mostrar planificación por máquina
            st.subheader("📋 Planificación Detallada por Máquina")
            
            dias_semana = [(fecha_inicio + timedelta(days=i)).strftime('%d/%m (%a)') for i in range(dias)]
            
            for maq in ['E1', 'E2', 'E3', 'E5', 'E8']:
                st.markdown(f"### 🖥️ Línea {maq}")
                
                # Crear tabla para esta máquina
                tabla_data = []
                for dia in range(dias):
                    tareas = plan[maq][dia]
                    if tareas:
                        for tarea in tareas:
                            tabla_data.append({
                                'Día': dias_semana[dia],
                                'Pedido': tarea['pedido'],
                                'Cliente': tarea['cliente'],
                                'Producto': tarea['producto'][:20] + "..." if len(tarea['producto']) > 20 else tarea['producto'],
                                'Cantidad': f"{tarea['cantidad']:,}",
                                'RT': "✅" if tarea['rt'] else "❌",
                                'Fecha Entrega': tarea['fecha_entrega']
                            })
                    else:
                        tabla_data.append({
                            'Día': dias_semana[dia],
                            'Pedido': '—',
                            'Cliente': '—',
                            'Producto': '—',
                            'Cantidad': '—',
                            'RT': '—',
                            'Fecha Entrega': '—'
                        })
                
                if tabla_data:
                    df_maq = pd.DataFrame(tabla_data)
                    st.dataframe(df_maq, use_container_width=True, height=300)
                else:
                    st.info(f"Sin producción planificada para {maq}")
                
                st.markdown("---")
            
            # Resumen de carga por día
            st.subheader("📊 Resumen de Producción Diaria")
            resumen_data = []
            for dia in range(dias):
                fila = {'Día': dias_semana[dia]}
                for maq in ['E1', 'E2', 'E3', 'E5', 'E8']:
                    total_dia = sum(t['cantidad'] for t in plan[maq][dia])
                    fila[maq] = f"{total_dia:,.0f}" if total_dia > 0 else "—"
                resumen_data.append(fila)
            
            df_resumen = pd.DataFrame(resumen_data)
            st.dataframe(df_resumen, use_container_width=True)

# ============================================
# PEDIDOS
# ============================================
elif menu == "📦 PEDIDOS":
    st.markdown("<h1>📦 Pedidos</h1>", unsafe_allow_html=True)
    
    if pedidos:
        df_ped = pd.DataFrame(pedidos)
        st.dataframe(df_ped[['numero', 'cliente_nombre', 'cantidad', 'fecha_entrega', 'lleva_rt']], use_container_width=True)
        
        # Botón para eliminar pedidos
        st.markdown("---")
        st.subheader("🗑️ Eliminar Pedido")
        pedido_a_eliminar = st.selectbox("Seleccionar pedido", [""] + [p['numero'] for p in pedidos])
        if pedido_a_eliminar and st.button("Eliminar Pedido"):
            for p in pedidos:
                if p['numero'] == pedido_a_eliminar:
                    try:
                        requests.delete(f"{SUPABASE_URL}/pedidos?id=eq.{p['id']}", headers=HEADERS)
                        st.success(f"Pedido {pedido_a_eliminar} eliminado")
                        st.rerun()
                    except:
                        st.error("Error al eliminar")
                    break
    else:
        st.info("No hay pedidos registrados")

# ============================================
# IMPORTAR PEDIDO
# ============================================
elif menu == "📄 IMPORTAR PEDIDO":
    st.markdown("<h1>📄 Importar Pedido</h1>", unsafe_allow_html=True)
    
    st.markdown("""
    <div style="background-color: #e2e8f0; padding: 15px; border-radius: 8px; margin-bottom: 20px;">
        <strong>📋 Instrucciones:</strong><br>
        1. Copia el texto del pedido (desde el PDF, email o Excel)<br>
        2. Pégalo en el cuadro de abajo<br>
        3. El sistema extraerá automáticamente SKUs, cantidades y detectará RT
    </div>
    """, unsafe_allow_html=True)
    
    with st.expander("📋 Ver formato de ejemplo"):
        st.code("""
1000895661880 RR-120 LULAS DE CALDEIRADA S/E 56.000 1 56.000
1000895561883 RR-120 LULAS RECHEADAS CALDEIRADA S/E 35.532 1 35.532
5603344651041 RR-120 LULAS DE CALDEIRADA RT10 GENERAL 220 100 22.000
        """)
    
    texto_pedido = st.text_area("📝 Texto del pedido:", height=200)
    
    if st.button("🔍 PROCESAR PEDIDO", type="secondary", use_container_width=True):
        if texto_pedido:
            with st.spinner("Procesando líneas..."):
                lineas = extraer_lineas(texto_pedido)
            if lineas:
                st.success(f"✅ {len(lineas)} líneas extraídas correctamente")
                st.dataframe(pd.DataFrame(lineas), use_container_width=True)
                st.session_state['lineas'] = lineas
            else:
                st.error("❌ No se encontraron líneas válidas")
        else:
            st.warning("⚠️ Pega el texto del pedido primero")
    
    if 'lineas' in st.session_state:
        lineas = st.session_state['lineas']
        total_latas = sum(l['cantidad'] for l in lineas)
        st.metric("📦 Total pedido", f"{total_latas:,} latas")
        
        col1, col2 = st.columns(2)
        with col1:
            pedido_numero = st.text_input("Número de pedido", "PEDIDO_NUEVO")
            fecha_entrega = st.date_input("Fecha de entrega", datetime.now() + timedelta(days=7))
        with col2:
            opciones = [c['nombre'] for c in clientes] if clientes else ["CLIENTE_TEST"]
            cliente = st.selectbox("Cliente", opciones)
        
        if st.button("💾 GUARDAR PEDIDO", type="primary", use_container_width=True):
            cliente_id = None
            for c in clientes:
                if c['nombre'] == cliente:
                    cliente_id = c['id']
                    break
            
            if cliente_id is None:
                st.error("❌ Cliente no encontrado. Ve a Supabase y añade el cliente.")
            else:
                guardados = 0
                for item in lineas:
                    if insert_data("pedidos", {
                        "numero": pedido_numero,
                        "cliente_id": cliente_id,
                        "fecha_entrega": str(fecha_entrega),
                        "cantidad": item['cantidad'],
                        "producto_sku": item['sku'],
                        "lleva_rt": 1 if item['lleva_rt'] else 0
                    }):
                        guardados += 1
                
                if guardados > 0:
                    st.success(f"✅ {guardados} líneas guardadas correctamente")
                    st.balloons()
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("❌ No se pudo guardar ningún pedido")
