import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
import re
import plotly.express as px
import plotly.graph_objects as go
import time

# Configuración de página - ESTILO TÉCNICO
st.set_page_config(
    page_title="LeanCan - Planificación Industrial",
    page_icon="🏭",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS PERSONALIZADO - ESTILO TÉCNICO INDUSTRIAL
st.markdown("""
<style>
    /* Estilo general técnico */
    .stApp {
        background-color: #f0f2f6;
    }
    
    /* Encabezados */
    h1 {
        color: #1a365d !important;
        font-weight: 700 !important;
        border-bottom: 3px solid #2c5282 !important;
        padding-bottom: 15px !important;
    }
    
    h2 {
        color: #2c5282 !important;
        font-weight: 600 !important;
        margin-top: 20px !important;
        border-left: 4px solid #4299e1 !important;
        padding-left: 15px !important;
    }
    
    h3 {
        color: #2d3748 !important;
        font-weight: 600 !important;
    }
    
    /* Tarjetas de métricas */
    .metric-card {
        background: linear-gradient(135deg, #1e3a5f 0%, #2c5282 100%);
        border-radius: 12px;
        padding: 20px;
        color: white;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        margin: 10px 0;
    }
    
    .metric-card h3 {
        color: white !important;
        font-size: 14px;
        margin: 0;
        opacity: 0.9;
    }
    
    .metric-card .value {
        font-size: 32px;
        font-weight: bold;
        margin: 10px 0 0 0;
    }
    
    .metric-card .unit {
        font-size: 12px;
        opacity: 0.8;
    }
    
    /* Máquina individual */
    .machine-card {
        background: white;
        border-radius: 10px;
        padding: 15px;
        margin: 10px 0;
        border-left: 4px solid;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    
    .machine-name {
        font-size: 20px;
        font-weight: bold;
    }
    
    .machine-status {
        font-size: 12px;
        padding: 2px 8px;
        border-radius: 20px;
        display: inline-block;
    }
    
    .status-online {
        background-color: #c6f6d5;
        color: #22543d;
    }
    
    .status-warning {
        background-color: #fefcbf;
        color: #744210;
    }
    
    .status-critical {
        background-color: #fed7d7;
        color: #742a2a;
    }
    
    /* Tablas */
    .dataframe {
        font-family: 'Courier New', monospace;
        font-size: 13px;
    }
    
    .dataframe th {
        background-color: #2c5282 !important;
        color: white !important;
        font-weight: 600 !important;
    }
    
    /* Sidebar */
    .css-1d391kg {
        background-color: #1a365d;
    }
    
    /* Botones */
    .stButton > button {
        background-color: #2c5282;
        color: white;
        font-weight: 600;
        border-radius: 8px;
        transition: all 0.3s;
    }
    
    .stButton > button:hover {
        background-color: #1a365d;
        transform: translateY(-2px);
    }
    
    /* Sidebar navigation */
    .sidebar-nav {
        padding: 20px 0;
    }
    
    .sidebar-nav-item {
        padding: 10px 15px;
        margin: 5px 0;
        border-radius: 8px;
        cursor: pointer;
        transition: all 0.3s;
    }
    
    .sidebar-nav-item:hover {
        background-color: rgba(255,255,255,0.1);
    }
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
            lineas.append({
                'sku': sku_match.group(1),
                'cantidad': cantidad,
                'lleva_rt': lleva_rt
            })
    return lineas

# ============================================
# FUNCIONES DE PLANIFICACIÓN
# ============================================
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
    
    return plan, saturacion, carga_total, carga_diaria

def mostrar_gantt(plan, fecha_inicio, dias):
    """Diagrama de Gantt técnico"""
    gantt_data = []
    colores = {'E1': '#1f77b4', 'E2': '#ff7f0e', 'E3': '#2ca02c', 'E5': '#d62728', 'E8': '#9467bd'}
    
    for maq in plan.keys():
        for dia in range(dias):
            tareas = plan[maq][dia]
            if tareas:
                total_dia = sum(t['cantidad'] for t in tareas)
                fecha = fecha_inicio + timedelta(days=dia)
                gantt_data.append({
                    'Máquina': maq,
                    'Día': dia,
                    'Fecha': fecha.strftime('%d/%m'),
                    'Producción': total_dia,
                    'Color': colores.get(maq, '#888')
                })
    
    if not gantt_data:
        st.info("No hay producción planificada", icon="ℹ️")
        return
    
    df_gantt = pd.DataFrame(gantt_data)
    fig = go.Figure()
    
    for maq in plan.keys():
        df_maq = df_gantt[df_gantt['Máquina'] == maq]
        if not df_maq.empty:
            fig.add_trace(go.Bar(
                x=df_maq['Día'],
                y=[maq] * len(df_maq),
                orientation='h',
                marker_color=colores.get(maq, '#888'),
                text=df_maq['Producción'].apply(lambda x: f"{x:,.0f}"),
                textposition='inside',
                hoverinfo='text',
                hovertext=df_maq.apply(lambda r: f"{r['Máquina']} - {r['Fecha']}<br>{r['Producción']:,.0f} latas", axis=1),
                name=maq,
                showlegend=True
            ))
    
    dias_semana = [(fecha_inicio + timedelta(days=i)).strftime('%a %d/%m') for i in range(dias)]
    fig.update_layout(
        title="📊 Diagrama de Gantt - Planificación Semanal",
        xaxis=dict(title="Día", tickmode='array', tickvals=list(range(dias)), ticktext=dias_semana),
        yaxis=dict(title="Línea de Producción", categoryorder='array', categoryarray=list(plan.keys())),
        height=500,
        barmode='stack',
        hovermode='closest',
        plot_bgcolor='#f7f9fc',
        paper_bgcolor='white',
        font=dict(family="Courier New, monospace", size=11)
    )
    fig.update_traces(textfont=dict(size=10, color='white'))
    st.plotly_chart(fig, use_container_width=True)

def mostrar_planilla_semanal(plan, fecha_inicio, dias, saturacion):
    """Planilla semanal estilo fábrica"""
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
    
    df_tabla = pd.DataFrame(tabla_data)
    
    # Formato profesional
    st.markdown("### 📋 Plan de Producción Semanal")
    st.dataframe(
        df_tabla,
        use_container_width=True,
        height=300,
        column_config={
            "Línea": st.column_config.TextColumn("Línea", width="small"),
            "Total": st.column_config.NumberColumn("Total Semana", format="%.0f"),
            "Utilización": st.column_config.TextColumn("Utilización", width="small"),
        }
    )

# ============================================
# CARGA DE DATOS
# ============================================
with st.spinner("🔄 Cargando datos del sistema..."):
    maquinas = get_data("maquinas")
    clientes = get_data("clientes")
    productos = get_data("productos")
    pedidos = get_data("pedidos")
    clientes_dict = {c['id']: c['nombre'] for c in clientes}
    for p in pedidos:
        p['cliente_nombre'] = clientes_dict.get(p.get('cliente_id', 0), 'Desconocido')

# ============================================
# SIDEBAR - NAVEGACIÓN TÉCNICA
# ============================================
st.sidebar.markdown("""
<div style="text-align: center; padding: 20px 0;">
    <h2 style="color: white;">🏭 LeanCan</h2>
    <p style="color: #a0aec0;">Sistema de Planificación Industrial</p>
    <hr style="border-color: #2c5282;">
</div>
""", unsafe_allow_html=True)

menu = st.sidebar.radio(
    "",
    ["📊 PANEL DE CONTROL", "🏭 LÍNEAS DE PRODUCCIÓN", "📅 PLANIFICACIÓN", "📦 PEDIDOS", "📄 IMPORTAR PEDIDO"],
    format_func=lambda x: x
)

st.sidebar.markdown("""
<hr style="border-color: #2c5282;">
<div style="padding: 15px; background-color: #2c5282; border-radius: 8px; margin-top: 20px;">
    <p style="color: white; font-size: 12px; margin: 0;">
        📊 Sistema en línea<br>
        🏭 5 líneas activas<br>
        📦 Base de datos Supabase
    </p>
</div>
""", unsafe_allow_html=True)

# ============================================
# 1. PANEL DE CONTROL TÉCNICO
# ============================================
if menu == "📊 PANEL DE CONTROL":
    st.markdown("<h1>📊 Panel de Control Industrial</h1>", unsafe_allow_html=True)
    
    # Métricas principales - estilo técnico
    col1, col2, col3, col4 = st.columns(4)
    
    total_pedidos = len(pedidos)
    total_latas = sum(p.get('cantidad', 0) for p in pedidos)
    pedidos_rt = sum(1 for p in pedidos if p.get('lleva_rt', False))
    pendientes = len([p for p in pedidos if p.get('estado') != 'completado'])
    
    with col1:
        st.markdown(f"""
        <div class="metric-card">
            <h3>📦 PEDIDOS ACTIVOS</h3>
            <div class="value">{total_pedidos}</div>
            <div class="unit">unidades</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown(f"""
        <div class="metric-card">
            <h3>🥫 TOTAL LATAS</h3>
            <div class="value">{total_latas:,.0f}</div>
            <div class="unit">latas</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown(f"""
        <div class="metric-card">
            <h3>📦 CON RT</h3>
            <div class="value">{pedidos_rt}</div>
            <div class="unit">pedidos</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        st.markdown(f"""
        <div class="metric-card">
            <h3>⏳ PENDIENTES</h3>
            <div class="value">{pendientes}</div>
            <div class="unit">por procesar</div>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Gráficos técnicos
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("<h3>📈 Volumen por Cliente</h3>", unsafe_allow_html=True)
        if pedidos:
            df_ped = pd.DataFrame(pedidos)
            top_clientes = df_ped.groupby('cliente_nombre')['cantidad'].sum().sort_values(ascending=False).head(5)
            fig = px.bar(x=top_clientes.values, y=top_clientes.index, orientation='h',
                         color=top_clientes.values, color_continuous_scale='Blues',
                         labels={'x': 'Latas', 'y': 'Cliente'})
            fig.update_layout(height=400, plot_bgcolor='#f7f9fc')
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No hay datos de pedidos")
    
    with col2:
        st.markdown("<h3>📅 Distribución por Fecha</h3>", unsafe_allow_html=True)
        if pedidos:
            df_ped = pd.DataFrame(pedidos)
            df_ped['fecha_entrega'] = pd.to_datetime(df_ped['fecha_entrega'])
            por_dia = df_ped.groupby(df_ped['fecha_entrega'].dt.date)['cantidad'].sum().reset_index()
            fig = px.line(por_dia, x='fecha_entrega', y='cantidad', markers=True,
                          labels={'fecha_entrega': 'Fecha', 'cantidad': 'Latas'})
            fig.update_traces(line_color='#2c5282', marker_color='#2c5282', marker_size=8)
            fig.update_layout(height=400, plot_bgcolor='#f7f9fc')
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No hay datos de pedidos")

# ============================================
# 2. LÍNEAS DE PRODUCCIÓN
# ============================================
elif menu == "🏭 LÍNEAS DE PRODUCCIÓN":
    st.markdown("<h1>🏭 Líneas de Producción</h1>", unsafe_allow_html=True)
    
    datos_maquinas = [
        {"nombre": "E1", "formato": "RR-120", "velocidad": 200, "capacidad": 54000, "carga": 65, "estado": "online"},
        {"nombre": "E2", "formato": "RR-120/RR-90", "velocidad": 120, "capacidad": 32400, "carga": 42, "estado": "online"},
        {"nombre": "E3", "formato": "RR-120", "velocidad": 200, "capacidad": 54000, "carga": 78, "estado": "warning"},
        {"nombre": "E5", "formato": "RT (Retráctil)", "velocidad": 125, "capacidad": 33750, "carga": 55, "estado": "online"},
        {"nombre": "E8", "formato": "RO-85", "velocidad": 180, "capacidad": 48600, "carga": 30, "estado": "online"}
    ]
    
    for m in datos_maquinas:
        estado_class = "status-online" if m['estado'] == "online" else "status-warning"
        color_border = "#2c5282" if m['estado'] == "online" else "#e53e3e"
        
        st.markdown(f"""
        <div class="machine-card" style="border-left-color: {color_border};">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <div>
                    <span class="machine-name">{m['nombre']}</span>
                    <span class="machine-status {estado_class}">● {m['estado'].upper()}</span>
                </div>
                <div style="font-family: monospace; font-size: 12px;">Formato: {m['formato']}</div>
            </div>
            <hr style="margin: 10px 0;">
            <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 15px;">
                <div>
                    <div style="font-size: 11px; color: #718096;">VELOCIDAD</div>
                    <div style="font-size: 20px; font-weight: bold;">{m['velocidad']} <span style="font-size: 12px;">latas/min</span></div>
                </div>
                <div>
                    <div style="font-size: 11px; color: #718096;">CAPACIDAD DIARIA</div>
                    <div style="font-size: 20px; font-weight: bold;">{m['capacidad']:,} <span style="font-size: 12px;">latas</span></div>
                </div>
                <div>
                    <div style="font-size: 11px; color: #718096;">CARGA ACTUAL</div>
                    <div style="font-size: 20px; font-weight: bold;">{m['carga']}%</div>
                    <progress value="{m['carga']}" max="100" style="width: 100%; height: 8px; border-radius: 4px;"></progress>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

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
                plan, saturacion, cargas, _ = generar_planificacion(pedidos, fecha_inicio, dias)
            
            # Gráfico de saturación
            st.markdown("<h3>📊 Saturación de Líneas</h3>", unsafe_allow_html=True)
            df_sat = pd.DataFrame([{"Línea": k, "Saturación": v} for k, v in saturacion.items()])
            fig = px.bar(df_sat, x="Línea", y="Saturación", text="Saturación",
                         color="Saturación", color_continuous_scale=["#2ecc71", "#f39c12", "#e74c3c"],
                         labels={"Saturación": "Utilización (%)"})
            fig.update_traces(textposition='outside')
            fig.update_layout(height=400, plot_bgcolor='#f7f9fc')
            st.plotly_chart(fig, use_container_width=True)
            
            # Gantt
            mostrar_gantt(plan, fecha_inicio, dias)
            
            # Planilla semanal
            mostrar_planilla_semanal(plan, fecha_inicio, dias, saturacion)

# ============================================
# 4. PEDIDOS
# ============================================
elif menu == "📦 PEDIDOS":
    st.markdown("<h1>📦 Gestión de Pedidos</h1>", unsafe_allow_html=True)
    
    if pedidos:
        df_pedidos = pd.DataFrame(pedidos)
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Pedidos", len(pedidos))
        with col2:
            st.metric("Total Latas", f"{df_pedidos['cantidad'].sum():,.0f}")
        with col3:
            st.metric("Pedidos con RT", df_pedidos['lleva_rt'].sum())
        
        st.markdown("---")
        st.dataframe(df_pedidos[['numero', 'cliente_nombre', 'cantidad', 'fecha_entrega', 'lleva_rt']], 
                    use_container_width=True)
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
1000898461845 RR-120 POTA GIGANTE EM CALDEIRADA S/E 23.688 1 23.688
5603344651041 RR-120 LULAS DE CALDEIRADA RT10 GENERAL 220 100 22.000
        """)
    
    texto_pedido = st.text_area("📝 Texto del pedido:", height=200)
    
    if st.button("🔍 PROCESAR PEDIDO", type="primary", use_container_width=True):
        if texto_pedido:
            with st.spinner("Procesando líneas..."):
                lineas = extraer_lineas(texto_pedido)
            
            if lineas:
                st.success(f"✅ {len(lineas)} líneas extraídas correctamente")
                st.dataframe(pd.DataFrame(lineas), use_container_width=True)
                
                total_latas = sum(l['cantidad'] for l in lineas)
                st.markdown(f"<div style='background-color: #2c5282; color: white; padding: 10px; border-radius: 8px; text-align: center; margin: 10px 0;'>📦 TOTAL PEDIDO: {total_latas:,} LATAS</div>", unsafe_allow_html=True)
                
                col1, col2 = st.columns(2)
                with col1:
                    pedido_numero = st.text_input("Número de pedido", "PEDIDO_NUEVO")
                    fecha_entrega = st.date_input("Fecha de entrega", datetime.now() + timedelta(days=7))
                with col2:
                    opciones = [c['nombre'] for c in clientes] if clientes else ["CLIENTE_TEST"]
                    cliente = st.selectbox("Cliente", opciones)
                
                if st.button("💾 GUARDAR PEDIDO", type="primary", use_container_width=True):
                    cliente_id = 1
                    for c in clientes:
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
                            "lleva_rt": 1 if item['lleva_rt'] else 0,
                            "estado": "pendiente"
                        })
                    
                    st.success(f"✅ Pedido {pedido_numero} guardado con {len(lineas)} líneas")
                    st.balloons()
                    time.sleep(1)
                    st.rerun()
            else:
                st.error("❌ No se encontraron líneas válidas en el texto")
        else:
            st.warning("⚠️ Pega el texto del pedido primero")
