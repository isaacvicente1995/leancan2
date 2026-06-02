import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
import re
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(page_title="LeanCan", page_icon="🥫", layout="wide")

st.title("🥫 LeanCan Scheduler")

# Configuración Supabase
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

# ============================================
# FUNCIONES DE PLANIFICACIÓN
# ============================================
def generar_planificacion(pedidos, maquinas, fecha_inicio, dias=7):
    """
    Genera planificación semanal: qué produce cada máquina cada día
    """
    # Capacidades diarias por máquina (latas/día)
    capacidad = {
        'E1': 54000,
        'E2': 32400,
        'E3': 54000,
        'E5': 33750,
        'E8': 48600
    }
    
    # Inicializar planificación
    plan = {maq: {i: [] for i in range(dias)} for maq in capacidad.keys()}
    carga_acumulada = {maq: 0 for maq in capacidad.keys()}
    
    # Ordenar pedidos por fecha de entrega y prioridad
    pedidos_ordenados = sorted(pedidos, key=lambda x: (x.get('fecha_entrega', '9999-12-31'), -x.get('cantidad', 0)))
    
    for pedido in pedidos_ordenados:
        cantidad = pedido.get('cantidad', 0)
        lleva_rt = pedido.get('lleva_rt', False)
        
        # Determinar máquina destino
        if lleva_rt:
            maquinas_destino = ['E5']
        else:
            maquinas_destino = ['E1', 'E3']  # Distribuir entre E1 y E3
        
        cantidad_restante = cantidad
        
        for maq in maquinas_destino:
            for dia in range(dias):
                disponible = capacidad[maq] - carga_acumulada[maq]
                if disponible <= 0:
                    continue
                
                asignar = min(cantidad_restante, disponible)
                if asignar > 0:
                    plan[maq][dia].append({
                        'pedido': pedido.get('numero', 'N/A'),
                        'cantidad': asignar,
                        'cliente': pedido.get('cliente_nombre', 'N/A'),
                        'rt': lleva_rt
                    })
                    carga_acumulada[maq] += asignar
                    cantidad_restante -= asignar
                    
                    if cantidad_restante <= 0:
                        break
            
            if cantidad_restante <= 0:
                break
    
    # Calcular saturación
    saturacion = {}
    for maq in capacidad:
        carga_total = carga_acumulada[maq]
        saturacion[maq] = round((carga_total / (capacidad[maq] * dias)) * 100, 1)
    
    return plan, saturacion, carga_acumulada

def generar_gantt(plan, dias, fecha_inicio):
    """
    Genera gráfico Gantt a partir de la planificación
    """
    colores = {'E1': '#1f77b4', 'E2': '#ff7f0e', 'E3': '#2ca02c', 'E5': '#d62728', 'E8': '#9467bd'}
    
    fig = go.Figure()
    
    for maquina in plan.keys():
        for dia in range(dias):
            tareas = plan[maquina][dia]
            if tareas:
                # Acumular tareas del día
                tarea_texto = "<br>".join([f"{t['pedido']}: {t['cantidad']:,}" for t in tareas[:3]])
                if len(tareas) > 3:
                    tarea_texto += f"<br>+{len(tareas)-3} más"
                
                fig.add_trace(go.Bar(
                    x=[dia],
                    y=[maquina],
                    orientation='h',
                    name=f"{maquina}",
                    marker_color=colores.get(maquina, '#888'),
                    text=tarea_texto,
                    textposition='inside',
                    textfont=dict(size=10, color='white'),
                    hoverinfo='text',
                    hovertext=f"{maquina} - Día {dia+1}<br>{tarea_texto}",
                    showlegend=False
                ))
    
    # Configurar layout
    dias_semana = [(fecha_inicio + timedelta(days=i)).strftime('%a %d/%m') for i in range(dias)]
    
    fig.update_layout(
        title="Distribución de Producción por Máquina y Día",
        xaxis=dict(
            title="Día",
            tickmode='array',
            tickvals=list(range(dias)),
            ticktext=dias_semana
        ),
        yaxis=dict(
            title="Máquina",
            categoryorder='array',
            categoryarray=list(plan.keys())
        ),
        height=500,
        barmode='stack'
    )
    
    return fig

def mostrar_planilla_semanal(plan, fecha_inicio, dias, saturacion):
    """
    Muestra planilla semanal en formato tabla
    """
    dias_semana = [(fecha_inicio + timedelta(days=i)).strftime('%d/%m (%a)') for i in range(dias)]
    
    st.subheader("📅 Planilla Semanal de Producción")
    
    # Crear DataFrame para mostrar
    data = []
    for maquina in plan.keys():
        fila = [maquina]
        total_semana = 0
        for dia in range(dias):
            tareas = plan[maquina][dia]
            if tareas:
                total_dia = sum(t['cantidad'] for t in tareas)
                total_semana += total_dia
                texto = f"{total_dia:,} latas<br>" + "<br>".join([f"{t['pedido']}" for t in tareas[:2]])
                if len(tareas) > 2:
                    texto += f"<br>+{len(tareas)-2} más"
            else:
                texto = "—"
                total_dia = 0
            fila.append(texto)
        fila.append(f"{total_semana:,}")
        fila.append(f"{saturacion.get(maquina, 0)}%")
        data.append(fila)
    
    # Crear DataFrame
    columnas = ['Máquina'] + dias_semana + ['Total Semana', 'Saturación']
    df_planilla = pd.DataFrame(data, columns=columnas)
    
    # Mostrar como HTML para permitir HTML en celdas
    st.markdown(df_planilla.to_html(escape=False, index=False), unsafe_allow_html=True)
    
    # Formato condicional con CSS
    st.markdown("""
    <style>
        table {
            width: 100%;
            border-collapse: collapse;
        }
        th, td {
            border: 1px solid #ddd;
            padding: 8px;
            text-align: left;
        }
        th {
            background-color: #4CAF50;
            color: white;
        }
        tr:nth-child(even) {
            background-color: #f2f2f2;
        }
    </style>
    """, unsafe_allow_html=True)

# ============================================
# FUNCIONES AUXILIARES
# ============================================
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
            num = int(c.replace('.', ''))
            if 1000 < num < 1000000:
                cantidad = num
                break
        lleva_rt = 'RT10' in linea or 'RT' in linea.upper()
        if sku_match and cantidad > 0:
            sku = sku_match.group(1)
            lineas.append({'sku': sku, 'cantidad': cantidad, 'lleva_rt': lleva_rt})
    return lineas

# ============================================
# CARGA DE DATOS
# ============================================
with st.spinner("Cargando datos..."):
    maquinas_data = get_data("maquinas")
    clientes_data = get_data("clientes")
    productos_data = get_data("productos")
    pedidos_data = get_data("pedidos")
    
    # Enriquecer pedidos con nombre de cliente
    clientes_dict = {c['id']: c['nombre'] for c in clientes_data}
    for p in pedidos_data:
        p['cliente_nombre'] = clientes_dict.get(p.get('cliente_id'), 'Desconocido')

# ============================================
# MENÚ PRINCIPAL
# ============================================
menu = st.sidebar.radio(
    "📋 MENÚ",
    ["📊 Dashboard", "🏭 Equipos", "📅 Planificación", "📦 Pedidos", "📄 Cargar Pedido"]
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
    
    st.markdown("---")
    
    # Gráfico de pedidos por día
    if pedidos_data:
        df_pedidos = pd.DataFrame(pedidos_data)
        df_pedidos['fecha_entrega'] = pd.to_datetime(df_pedidos['fecha_entrega'])
        pedidos_por_dia = df_pedidos.groupby(df_pedidos['fecha_entrega'].dt.date)['cantidad'].sum().reset_index()
        
        fig = px.bar(pedidos_por_dia, x='fecha_entrega', y='cantidad', 
                     title='📦 Pedidos por fecha de entrega',
                     labels={'fecha_entrega': 'Fecha', 'cantidad': 'Latas'})
        st.plotly_chart(fig, use_container_width=True)

# ============================================
# EQUIPOS
# ============================================
elif menu == "🏭 Equipos":
    st.header("🏭 Estado de Equipos")
    
    equipos = [
        {"nombre": "E1", "formato": "RR-120", "velocidad": 200, "capacidad": 54000, "color": "#1f77b4"},
        {"nombre": "E2", "formato": "RR-120/RR-90", "velocidad": 120, "capacidad": 32400, "color": "#ff7f0e"},
        {"nombre": "E3", "formato": "RR-120", "velocidad": 200, "capacidad": 54000, "color": "#2ca02c"},
        {"nombre": "E5", "formato": "RT (Retráctil)", "velocidad": 125, "capacidad": 33750, "color": "#d62728"},
        {"nombre": "E8", "formato": "RO-85", "velocidad": 180, "capacidad": 48600, "color": "#9467bd"}
    ]
    
    for eq in equipos:
        with st.container():
            col1, col2, col3, col4 = st.columns([2, 2, 2, 1])
            with col1:
                st.subheader(f"🖥️ {eq['nombre']}")
                st.caption(f"Formatos: {eq['formato']}")
            with col2:
                st.metric("⚡ Velocidad", f"{eq['velocidad']} latas/min")
            with col3:
                st.metric("📦 Capacidad", f"{eq['capacidad']:,} latas/día")
            with col4:
                # Carga simulada (en producción se calcularía real)
                carga = 65 if eq['nombre'] == 'E1' else 42 if eq['nombre'] == 'E2' else 78 if eq['nombre'] == 'E3' else 55 if eq['nombre'] == 'E5' else 30
                st.progress(carga / 100)
                st.caption(f"{carga}% de carga")
            st.markdown("---")

# ============================================
# PLANIFICACIÓN (GANTT + PLANILLA)
# ============================================
elif menu == "📅 Planificación":
    st.header("📅 Planificación de Producción")
    
    # Controles
    col1, col2 = st.columns([2, 1])
    with col1:
        fecha_inicio = st.date_input("Fecha de inicio", datetime.now())
    with col2:
        dias = st.selectbox("Horizonte (días)", [5, 7, 10, 14], index=1)
    
    if st.button("🔄 Generar Planificación", type="primary"):
        if not pedidos_data:
            st.warning("No hay pedidos para planificar")
        else:
            with st.spinner("Generando planificación..."):
                plan, saturacion, cargas = generar_planificacion(pedidos_data, maquinas_data, fecha_inicio, dias)
            
            # Gráfico de saturación
            st.subheader("📊 Saturación de Máquinas")
            df_sat = pd.DataFrame([{"Máquina": k, "Saturación %": v} for k, v in saturacion.items()])
            fig_sat = px.bar(df_sat, x="Máquina", y="Saturación %", 
                            text="Saturación %", color="Saturación %",
                            color_continuous_scale=["green", "yellow", "red"],
                            title="Carga de trabajo semanal")
            fig_sat.update_traces(textposition='outside')
            st.plotly_chart(fig_sat, use_container_width=True)
            
            # Diagrama de Gantt
            st.subheader("📊 Diagrama de Gantt")
            fig_gantt = generar_gantt(plan, dias, fecha_inicio)
            st.plotly_chart(fig_gantt, use_container_width=True)
            
            # Planilla semanal
            mostrar_planilla_semanal(plan, fecha_inicio, dias, saturacion)
            
            # Resumen de cargas
            st.subheader("📊 Resumen de cargas por máquina")
            col1, col2, col3, col4, col5 = st.columns(5)
            col1.metric("E1", f"{cargas.get('E1', 0):,} latas", f"{saturacion.get('E1', 0)}%")
            col2.metric("E2", f"{cargas.get('E2', 0):,} latas", f"{saturacion.get('E2', 0)}%")
            col3.metric("E3", f"{cargas.get('E3', 0):,} latas", f"{saturacion.get('E3', 0)}%")
            col4.metric("E5", f"{cargas.get('E5', 0):,} latas", f"{saturacion.get('E5', 0)}%")
            col5.metric("E8", f"{cargas.get('E8', 0):,} latas", f"{saturacion.get('E8', 0)}%")

# ============================================
# PEDIDOS
# ============================================
elif menu == "📦 Pedidos":
    st.header("📝 Lista de Pedidos")
    if pedidos_data:
        df_pedidos = pd.DataFrame(pedidos_data)
        st.dataframe(df_pedidos, use_container_width=True)
        
        # Estadísticas
        total_latas = df_pedidos['cantidad'].sum()
        pedidos_rt = df_pedidos['lleva_rt'].sum()
        st.info(f"📊 Total: {len(pedidos_data)} pedidos | {total_latas:,} latas | {pedidos_rt} con RT")
    else:
        st.info("No hay pedidos registrados")

# ============================================
# CARGAR PEDIDO
# ============================================
elif menu == "📄 Cargar Pedido":
    st.header("📄 Cargar Pedido")
    
    with st.expander("📋 Ejemplo - Copia este texto"):
        st.code("""
1000895661880 RR-120 LULAS DE CALDEIRADA S/E 56.000 1 56.000
1000895561883 RR-120 LULAS RECHEADAS CALDEIRADA S/E 35.532 1 35.532
1000898461845 RR-120 POTA GIGANTE EM CALDEIRADA S/E 23.688 1 23.688
5603344651041 RR-120 LULAS DE CALDEIRADA RT10 GENERAL 220 100 22.000
        """)
    
    texto_pedido = st.text_area("Pega aquí el texto del pedido:", height=200)
    
    if st.button("🔍 Procesar Pedido", type="primary"):
        if texto_pedido:
            with st.spinner("Procesando..."):
                lineas = extraer_lineas(texto_pedido)
            
            if lineas:
                st.success(f"✅ Se encontraron {len(lineas)} líneas")
                st.dataframe(pd.DataFrame(lineas), use_container_width=True)
                
                col1, col2 = st.columns(2)
                with col1:
                    pedido_numero = st.text_input("Número de pedido", "PEDIDO_NUEVO")
                    fecha_entrega = st.date_input("Fecha de entrega", datetime.now())
                with col2:
                    opciones = [c['nombre'] for c in clientes_data] if clientes_data else ["CLIENTE_TEST"]
                    cliente = st.selectbox("Cliente", opciones)
                
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
                    
                    st.success(f"✅ Pedido guardado con {len(lineas)} líneas")
                    st.balloons()
            else:
                st.error("No se encontraron líneas")
