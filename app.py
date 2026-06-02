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
    h1 { color: #1a365d !important; font-weight: 700 !important; border-bottom: 3px solid #2c5282 !important; padding-bottom: 15px !important; }
    h2 { color: #2c5282 !important; font-weight: 600 !important; margin-top: 20px !important; border-left: 4px solid #4299e1 !important; padding-left: 15px !important; }
    .metric-card { background: linear-gradient(135deg, #1e3a5f 0%, #2c5282 100%); border-radius: 12px; padding: 20px; color: white; box-shadow: 0 4px 6px rgba(0,0,0,0.1); margin: 10px 0; }
    .metric-card h3 { color: white !important; font-size: 14px; margin: 0; opacity: 0.9; }
    .metric-card .value { font-size: 32px; font-weight: bold; margin: 10px 0 0 0; }
    .machine-card { background: white; border-radius: 10px; padding: 15px; margin: 10px 0; border-left: 4px solid; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
    .machine-name { font-size: 20px; font-weight: bold; }
    .machine-status { font-size: 12px; padding: 2px 8px; border-radius: 20px; display: inline-block; }
    .status-online { background-color: #c6f6d5; color: #22543d; }
    .stButton > button { background-color: #2c5282; color: white; font-weight: 600; border-radius: 8px; transition: all 0.3s; }
    .stButton > button:hover { background-color: #1a365d; transform: translateY(-2px); }
</style>
""", unsafe_allow_html=True)

# ============================================
# CONFIGURACIÓN SUPABASE
# ============================================
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

def delete_data(table, id_field, id_value):
    try:
        response = requests.delete(f"{SUPABASE_URL}/{table}?{id_field}=eq.{id_value}", headers=HEADERS)
        return response.status_code == 204
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

def calcular_carga_real(pedidos):
    """Calcula la carga real de cada máquina basada en pedidos existentes"""
    capacidades = {'E1': 54000, 'E2': 32400, 'E3': 54000, 'E5': 33750, 'E8': 48600}
    carga = {'E1': 0, 'E2': 0, 'E3': 0, 'E5': 0, 'E8': 0}
    
    for pedido in pedidos:
        cantidad = pedido.get('cantidad', 0)
        lleva_rt = pedido.get('lleva_rt', False)
        
        if lleva_rt:
            carga['E5'] += cantidad
        else:
            # Distribuir entre E1 y E3 según carga actual
            if carga['E1'] <= carga['E3']:
                carga['E1'] += cantidad
            else:
                carga['E3'] += cantidad
    
    # Calcular porcentajes
    porcentajes = {}
    for maq in capacidades:
        porcentajes[maq] = round((carga[maq] / capacidades[maq]) * 100, 1) if capacidades[maq] > 0 else 0
    
    return carga, porcentajes

def generar_planificacion(pedidos, fecha_inicio, dias=7):
    capacidades = {'E1': 54000, 'E2': 32400, 'E3': 54000, 'E5': 33750, 'E8': 48600}
    plan = {maq: {i: [] for i in range(dias)} for maq in capacidades.keys()}
    carga_diaria = {maq: {i: 0 for i in range(dias)} for maq in capacidades.keys()}
    carga_total = {maq: 0 for maq in capacidades.keys()}
    
    pedidos_ordenados = sorted(pedidos, key=lambda x: (x.get('fecha_entrega', '9999-12-31'), -x.get('cantidad', 0)))
    
    for pedido in pedidos_ordenados:
        cantidad = pedido.get('cantidad', 0)
        lleva_rt = pedido.get('lleva_rt', False)
        pedido_numero = pedido.get('numero', 'N/A')
        
        if lleva_rt:
            maquinas_destino = ['E5']
        else:
            maquinas_destino = ['E1', 'E3']
        
        cantidad_restante = cantidad
        for maq in maquinas_destino:
            for dia in range(dias):
                disponible = capacidades[maq] - carga_diaria[maq][dia]
                if disponible <= 0:
                    continue
                asignar = min(cantidad_restante, disponible)
                if asignar > 0:
                    plan[maq][dia].append({'pedido': pedido_numero, 'cantidad': asignar})
                    carga_diaria[maq][dia] += asignar
                    carga_total[maq] += asignar
                    cantidad_restante -= asignar
                    if cantidad_restante <= 0:
                        break
            if cantidad_restante <= 0:
                break
    
    saturacion = {}
    for maq in capacidades:
        capacidad_semanal = capacidades[maq] * dias
        saturacion[maq] = round((carga_total[maq] / capacidad_semanal) * 100, 1) if capacidad_semanal > 0 else 0
    
    return plan, saturacion, carga_total

def mostrar_gantt(plan, fecha_inicio, dias):
    gantt_data = []
    colores = {'E1': '#1f77b4', 'E2': '#ff7f0e', 'E3': '#2ca02c', 'E5': '#d62728', 'E8': '#9467bd'}
    
    for maq in plan.keys():
        for dia in range(dias):
            tareas = plan[maq][dia]
            if tareas:
                total_dia = sum(t['cantidad'] for t in tareas)
                fecha = fecha_inicio + timedelta(days=dia)
                gantt_data.append({'Máquina': maq, 'Día': dia, 'Fecha': fecha.strftime('%d/%m'), 'Producción': total_dia})
    
    if not gantt_data:
        st.info("No hay producción planificada", icon="ℹ️")
        return
    
    df_gantt = pd.DataFrame(gantt_data)
    fig = go.Figure()
    
    for maq in plan.keys():
        df_maq = df_gantt[df_gantt['Máquina'] == maq]
        if not df_maq.empty:
            fig.add_trace(go.Bar(
                x=df_maq['Día'], y=[maq] * len(df_maq), orientation='h',
                marker_color=colores.get(maq, '#888'),
                text=df_maq['Producción'].apply(lambda x: f"{x:,.0f}"),
                textposition='inside', name=maq, showlegend=True
            ))
    
    dias_semana = [(fecha_inicio + timedelta(days=i)).strftime('%a %d/%m') for i in range(dias)]
    fig.update_layout(
        title="Distribución de Producción por Máquina",
        xaxis=dict(title="Día", tickmode='array', tickvals=list(range(dias)), ticktext=dias_semana),
        yaxis=dict(title="Línea", categoryorder='array', categoryarray=list(plan.keys())),
        height=500, barmode='stack'
    )
    st.plotly_chart(fig, use_container_width=True)

def mostrar_planilla_semanal(plan, fecha_inicio, dias, saturacion):
    dias_semana = [(fecha_inicio + timedelta(days=i)).strftime('%a %d/%m') for i in range(dias)]
    tabla_data = []
    for maq in plan.keys():
        fila = {'Línea': maq}
        total_semana = 0
        for dia in range(dias):
            tareas = plan[maq][dia]
            total_dia = sum(t['cantidad'] for t in tareas) if tareas else 0
            total_semana += total_dia
            fila[dias_semana[dia]] = f"{total_dia:,.0f}" if total_dia > 0 else "—"
        fila['Total'] = f"{total_semana:,.0f}"
        fila['Utilización'] = f"{saturacion.get(maq, 0)}%"
        tabla_data.append(fila)
    st.dataframe(pd.DataFrame(tabla_data), use_container_width=True, height=300)

# ============================================
# CARGA DE DATOS REALES
# ============================================
with st.spinner("🔄 Cargando datos del sistema..."):
    maquinas = get_data("maquinas")
    clientes = get_data("clientes")
    productos = get_data("productos")
    pedidos = get_data("pedidos")
    clientes_dict = {c['id']: c['nombre'] for c in clientes}
    for p in pedidos:
        p['cliente_nombre'] = clientes_dict.get(p.get('cliente_id', 0), 'Desconocido')

# Calcular carga real de máquinas
carga_real, porcentaje_carga = calcular_carga_real(pedidos)

# ============================================
# SIDEBAR
# ============================================
st.sidebar.markdown("""
<div style="text-align: center; padding: 20px 0;">
    <h2 style="color: white;">🏭 LeanCan</h2>
    <p style="color: #a0aec0;">Sistema de Planificación Industrial</p>
    <hr style="border-color: #2c5282;">
</div>
""", unsafe_allow_html=True)

menu = st.sidebar.radio("", ["📊 PANEL DE CONTROL", "🏭 LÍNEAS DE PRODUCCIÓN", "📅 PLANIFICACIÓN", "📦 PEDIDOS", "📄 IMPORTAR PEDIDO"])

# ============================================
# 1. PANEL DE CONTROL
# ============================================
if menu == "📊 PANEL DE CONTROL":
    st.markdown("<h1>📊 Panel de Control Industrial</h1>", unsafe_allow_html=True)
    
    col1, col2, col3, col4 = st.columns(4)
    total_pedidos = len(pedidos)
    total_latas = sum(p.get('cantidad', 0) for p in pedidos)
    pedidos_rt = sum(1 for p in pedidos if p.get('lleva_rt', False))
    pendientes = len([p for p in pedidos if p.get('estado') != 'completado'])
    
    with col1:
        st.markdown(f"<div class='metric-card'><h3>📦 PEDIDOS ACTIVOS</h3><div class='value'>{total_pedidos}</div></div>", unsafe_allow_html=True)
    with col2:
        st.markdown(f"<div class='metric-card'><h3>🥫 TOTAL LATAS</h3><div class='value'>{total_latas:,.0f}</div></div>", unsafe_allow_html=True)
    with col3:
        st.markdown(f"<div class='metric-card'><h3>📦 CON RT</h3><div class='value'>{pedidos_rt}</div></div>", unsafe_allow_html=True)
    with col4:
        st.markdown(f"<div class='metric-card'><h3>⏳ PENDIENTES</h3><div class='value'>{pendientes}</div></div>", unsafe_allow_html=True)
    
    st.markdown("---")
    
    if pedidos:
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("<h3>📈 Volumen por Cliente</h3>", unsafe_allow_html=True)
            df_ped = pd.DataFrame(pedidos)
            top_clientes = df_ped.groupby('cliente_nombre')['cantidad'].sum().sort_values(ascending=False).head(5)
            fig = px.bar(x=top_clientes.values, y=top_clientes.index, orientation='h', color=top_clientes.values, color_continuous_scale='Blues')
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            st.markdown("<h3>📅 Distribución por Fecha</h3>", unsafe_allow_html=True)
            df_ped['fecha_entrega'] = pd.to_datetime(df_ped['fecha_entrega'])
            por_dia = df_ped.groupby(df_ped['fecha_entrega'].dt.date)['cantidad'].sum().reset_index()
            fig = px.line(por_dia, x='fecha_entrega', y='cantidad', markers=True)
            fig.update_traces(line_color='#2c5282', marker_color='#2c5282')
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True)

# ============================================
# 2. LÍNEAS DE PRODUCCIÓN (CON CARGA REAL)
# ============================================
elif menu == "🏭 LÍNEAS DE PRODUCCIÓN":
    st.markdown("<h1>🏭 Líneas de Producción</h1>", unsafe_allow_html=True)
    
    # Datos técnicos de las máquinas
    maquinas_info = {
        'E1': {'formato': 'RR-120', 'velocidad': 200, 'capacidad': 54000},
        'E2': {'formato': 'RR-120/RR-90', 'velocidad': 120, 'capacidad': 32400},
        'E3': {'formato': 'RR-120', 'velocidad': 200, 'capacidad': 54000},
        'E5': {'formato': 'RT (Retráctil)', 'velocidad': 125, 'capacidad': 33750},
        'E8': {'formato': 'RO-85', 'velocidad': 180, 'capacidad': 48600}
    }
    
    for maq in ['E1', 'E2', 'E3', 'E5', 'E8']:
        info = maquinas_info[maq]
        carga_actual = porcentaje_carga.get(maq, 0)
        
        # Determinar color según carga
        if carga_actual < 50:
            estado = "online"
            estado_texto = "● NORMAL"
            color_border = "#2c5282"
        elif carga_actual < 80:
            estado = "warning"
            estado_texto = "● MEDIA"
            color_border = "#ed8936"
        else:
            estado = "critical"
            estado_texto = "● ALTA"
            color_border = "#e53e3e"
        
        st.markdown(f"""
        <div class="machine-card" style="border-left-color: {color_border};">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <div>
                    <span class="machine-name">{maq}</span>
                    <span class="machine-status status-{estado}">{estado_texto}</span>
                </div>
                <div style="font-family: monospace;">Formato: {info['formato']}</div>
            </div>
            <hr>
            <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 15px;">
                <div><div style="font-size: 11px; color: #718096;">VELOCIDAD</div><div style="font-size: 20px; font-weight: bold;">{info['velocidad']} <span style="font-size: 12px;">latas/min</span></div></div>
                <div><div style="font-size: 11px; color: #718096;">CAPACIDAD DIARIA</div><div style="font-size: 20px; font-weight: bold;">{info['capacidad']:,} <span style="font-size: 12px;">latas</span></div></div>
                <div><div style="font-size: 11px; color: #718096;">CARGA ACTUAL</div><div style="font-size: 20px; font-weight: bold;">{carga_actual}%</div><progress value="{carga_actual}" max="100" style="width: 100%; height: 8px; border-radius: 4px;"></progress></div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    # Mostrar resumen de carga total
    st.markdown("---")
    st.markdown("<h3>📊 Resumen de Carga</h3>", unsafe_allow_html=True)
    df_carga = pd.DataFrame([{"Línea": k, "Carga": v, "Capacidad": maquinas_info[k]['capacidad'], "Latas": carga_real[k]} for k, v in porcentaje_carga.items()])
    fig = px.bar(df_carga, x="Línea", y="Carga", text="Carga", color="Carga", color_continuous_scale=["#2ecc71", "#f39c12", "#e74c3c"])
    fig.update_traces(textposition='outside')
    fig.update_layout(height=400)
    st.plotly_chart(fig, use_container_width=True)

# ============================================
# 3. PLANIFICACIÓN
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
            with st.spinner("Calculando plan óptimo..."):
                plan, saturacion, cargas = generar_planificacion(pedidos, fecha_inicio, dias)
            
            st.markdown("<h3>📊 Saturación de Líneas</h3>", unsafe_allow_html=True)
            df_sat = pd.DataFrame([{"Línea": k, "Saturación": v} for k, v in saturacion.items()])
            fig = px.bar(df_sat, x="Línea", y="Saturación", text="Saturación", color="Saturación", color_continuous_scale=["#2ecc71", "#f39c12", "#e74c3c"])
            fig.update_traces(textposition='outside')
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True)
            
            mostrar_gantt(plan, fecha_inicio, dias)
            mostrar_planilla_semanal(plan, fecha_inicio, dias, saturacion)

# ============================================
# 4. PEDIDOS
# ============================================
elif menu == "📦 PEDIDOS":
    st.markdown("<h1>📦 Gestión de Pedidos</h1>", unsafe_allow_html=True)
    
    if pedidos:
        df_pedidos = pd.DataFrame(pedidos)
        col1, col2, col3 = st.columns(3)
        with col1: st.metric("Total Pedidos", len(pedidos))
        with col2: st.metric("Total Latas", f"{df_pedidos['cantidad'].sum():,.0f}")
        with col3: st.metric("Pedidos con RT", df_pedidos['lleva_rt'].sum())
        st.markdown("---")
        st.dataframe(df_pedidos[['numero', 'cliente_nombre', 'cantidad', 'fecha_entrega', 'lleva_rt']], use_container_width=True)
    else:
        st.info("No hay pedidos registrados")

# ============================================
# 5. IMPORTAR PEDIDO
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
                st.session_state['lineas_procesadas'] = lineas
            else:
                st.error("❌ No se encontraron líneas válidas")
        else:
            st.warning("⚠️ Pega el texto del pedido primero")
    
    if 'lineas_procesadas' in st.session_state:
        lineas = st.session_state['lineas_procesadas']
        total_latas = sum(l['cantidad'] for l in lineas)
        st.markdown(f"<div style='background-color: #2c5282; color: white; padding: 10px; border-radius: 8px; text-align: center;'>📦 TOTAL PEDIDO: {total_latas:,} LATAS</div>", unsafe_allow_html=True)
        
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
                        "lleva_rt": 1 if item['lleva_rt'] else 0,
                        "estado": "pendiente"
                    }):
                        guardados += 1
                if guardados > 0:
                    st.success(f"✅ {guardados} líneas guardadas correctamente")
                    st.balloons()
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("❌ No se pudo guardar ningún pedido")
