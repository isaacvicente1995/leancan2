
import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
import re
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(page_title="LeanCan", page_icon="🥫", layout="wide")

st.title("🥫 LeanCan Scheduler - Planificación de Producción")

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

# ============================================
# FUNCIONES BASE DE DATOS
# ============================================
def get_data(table, filters=None):
    url = f"{SUPABASE_URL}/{table}"
    if filters:
        url += f"?{filters}"
    try:
        response = requests.get(url, headers=HEADERS)
        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"Error {response.status_code}: {response.text}")
            return []
    except Exception as e:
        st.error(f"Error de conexión: {e}")
        return []

def insert_data(table, data):
    try:
        response = requests.post(f"{SUPABASE_URL}/{table}", headers=HEADERS, json=data)
        if response.status_code in [200, 201]:
            return True
        else:
            st.error(f"Error al insertar: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        st.error(f"Error: {e}")
        return False

def delete_data(table, id_field, id_value):
    try:
        response = requests.delete(f"{SUPABASE_URL}/{table}?{id_field}=eq.{id_value}", headers=HEADERS)
        return response.status_code == 204
    except:
        return False

# ============================================
# FUNCIONES DE PLANIFICACIÓN
# ============================================
def generar_planificacion(pedidos, fecha_inicio, dias=7):
    """
    Genera planificación de producción
    Retorna: plan (por máquina y día), saturacion, carga_acumulada
    """
    # Capacidades diarias por máquina (latas/día)
    capacidades = {
        'E1': 54000,
        'E2': 32400,
        'E3': 54000,
        'E5': 33750,
        'E8': 48600
    }
    
    # Inicializar planificación
    plan = {maq: {i: [] for i in range(dias)} for maq in capacidades.keys()}
    carga_diaria = {maq: {i: 0 for i in range(dias)} for maq in capacidades.keys()}
    carga_total = {maq: 0 for maq in capacidades.keys()}
    
    # Ordenar pedidos: primero los más urgentes (fecha más cercana)
    pedidos_ordenados = sorted(pedidos, key=lambda x: (x.get('fecha_entrega', '9999-12-31'), -x.get('cantidad', 0)))
    
    for pedido in pedidos_ordenados:
        cantidad = pedido.get('cantidad', 0)
        lleva_rt = pedido.get('lleva_rt', False)
        pedido_numero = pedido.get('numero', 'N/A')
        cliente = pedido.get('cliente_nombre', 'N/A')
        fecha_entrega = pedido.get('fecha_entrega', '')
        
        # Determinar máquinas destino
        if lleva_rt:
            maquinas_destino = ['E5']
        else:
            maquinas_destino = ['E1', 'E3']  # Distribuir entre E1 y E3
        
        cantidad_restante = cantidad
        
        for maq in maquinas_destino:
            for dia in range(dias):
                disponible = capacidades[maq] - carga_diaria[maq][dia]
                if disponible <= 0:
                    continue
                
                asignar = min(cantidad_restante, disponible)
                if asignar > 0:
                    plan[maq][dia].append({
                        'pedido': pedido_numero,
                        'cantidad': asignar,
                        'cliente': cliente,
                        'rt': lleva_rt,
                        'fecha_entrega': fecha_entrega
                    })
                    carga_diaria[maq][dia] += asignar
                    carga_total[maq] += asignar
                    cantidad_restante -= asignar
                    
                    if cantidad_restante <= 0:
                        break
            
            if cantidad_restante <= 0:
                break
    
    # Calcular saturación semanal
    saturacion = {}
    for maq in capacidades:
        capacidad_semanal = capacidades[maq] * dias
        saturacion[maq] = round((carga_total[maq] / capacidad_semanal) * 100, 1) if capacidad_semanal > 0 else 0
    
    return plan, saturacion, carga_total, carga_diaria

def mostrar_gantt(plan, fecha_inicio, dias):
    """Muestra diagrama de Gantt de la planificación"""
    
    # Crear datos para el Gantt
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
                    'Total latas': total_dia,
                    'Tareas': ', '.join([f"{t['pedido']}: {t['cantidad']:,}" for t in tareas[:3]]),
                    'Color': colores.get(maq, '#888')
                })
    
    if not gantt_data:
        st.info("No hay producción planificada")
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
                text=df_maq['Total latas'].apply(lambda x: f"{x:,}"),
                textposition='inside',
                hoverinfo='text',
                hovertext=df_maq.apply(lambda r: f"{r['Máquina']} - {r['Fecha']}<br>{r['Tareas']}", axis=1),
                name=maq,
                showlegend=True
            ))
    
    dias_semana = [(fecha_inicio + timedelta(days=i)).strftime('%a %d/%m') for i in range(dias)]
    
    fig.update_layout(
        title="Distribución de Producción por Máquina",
        xaxis=dict(title="Día", tickmode='array', tickvals=list(range(dias)), ticktext=dias_semana),
        yaxis=dict(title="Máquina", categoryorder='array', categoryarray=list(plan.keys())),
        height=500,
        barmode='stack',
        hovermode='closest'
    )
    
    st.plotly_chart(fig, use_container_width=True)

def mostrar_planilla_semanal(plan, fecha_inicio, dias, saturacion):
    """Muestra planilla semanal en formato tabla"""
    
    dias_semana = [(fecha_inicio + timedelta(days=i)).strftime('%d/%m (%a)') for i in range(dias)]
    
    st.subheader("📅 Planilla Semanal de Producción")
    
    # Crear datos para la tabla
    tabla_data = []
    for maq in plan.keys():
        fila = {'Máquina': maq}
        total_semana = 0
        for dia in range(dias):
            tareas = plan[maq][dia]
            if tareas:
                total_dia = sum(t['cantidad'] for t in tareas)
                total_semana += total_dia
                # Formato: cantidad + pedidos
                pedidos_text = ', '.join([f"{t['pedido']}" for t in tareas[:2]])
                if len(tareas) > 2:
                    pedidos_text += f" +{len(tareas)-2}"
                fila[dias_semana[dia]] = f"{total_dia:,}\n({pedidos_text})"
            else:
                fila[dias_semana[dia]] = "—"
        fila['Total Semana'] = f"{total_semana:,}"
        fila['Saturación'] = f"{saturacion.get(maq, 0)}%"
        tabla_data.append(fila)
    
    df_tabla = pd.DataFrame(tabla_data)
    
    # Mostrar tabla con formato
    st.dataframe(df_tabla, use_container_width=True, height=400)

# ============================================
# FUNCIONES DE EXTRACCIÓN DE PEDIDOS
# ============================================
def extraer_lineas(texto):
    """Extrae líneas del pedido desde texto"""
    lineas = []
    # Patrones para SKU (13 dígitos o 10 dígitos)
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
        
        lleva_rt = 'RT10' in linea or 'RT' in linea.upper() or 'retractil' in linea.lower()
        
        if sku_match and cantidad > 0:
            lineas.append({
                'sku': sku_match.group(1),
                'cantidad': cantidad,
                'lleva_rt': lleva_rt
            })
    
    return lineas

# ============================================
# CARGA DE DATOS INICIAL
# ============================================
with st.spinner("Cargando datos de la base de datos..."):
    maquinas = get_data("maquinas")
    clientes = get_data("clientes")
    productos = get_data("productos")
    pedidos = get_data("pedidos")
    
    # Crear diccionario de clientes para nombres
    clientes_dict = {c['id']: c['nombre'] for c in clientes}
    # Enriquecer pedidos con nombre del cliente
    for p in pedidos:
        p['cliente_nombre'] = clientes_dict.get(p.get('cliente_id', 0), 'Desconocido')

# ============================================
# SIDEBAR - MENÚ PRINCIPAL
# ============================================
st.sidebar.markdown("## 📋 Menú Principal")
menu = st.sidebar.radio(
    "",
    ["📊 Dashboard", "🏭 Máquinas", "📅 Planificación", "📦 Pedidos", "📄 Cargar Pedido"]
)

# ============================================
# 1. DASHBOARD
# ============================================
if menu == "📊 Dashboard":
    st.header("📊 Dashboard de Producción")
    
    # Métricas principales
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("🏭 Máquinas", len(maquinas))
    with col2:
        st.metric("👥 Clientes", len(clientes))
    with col3:
        st.metric("📦 Productos", len(productos))
    with col4:
        st.metric("📝 Pedidos Activos", len([p for p in pedidos if p.get('estado') != 'completado']))
    
    st.markdown("---")
    
    if pedidos:
        # Gráfico de pedidos por cantidad
        df_pedidos = pd.DataFrame(pedidos)
        df_pedidos['fecha_entrega'] = pd.to_datetime(df_pedidos['fecha_entrega'])
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Top clientes
            top_clientes = df_pedidos.groupby('cliente_nombre')['cantidad'].sum().sort_values(ascending=False).head(5)
            fig1 = px.bar(x=top_clientes.values, y=top_clientes.index, orientation='h',
                          title="Top 5 Clientes por Volumen", labels={'x': 'Latas', 'y': 'Cliente'})
            st.plotly_chart(fig1, use_container_width=True)
        
        with col2:
            # Pedidos por fecha
            pedidos_por_dia = df_pedidos.groupby(df_pedidos['fecha_entrega'].dt.date)['cantidad'].sum().reset_index()
            fig2 = px.line(pedidos_por_dia, x='fecha_entrega', y='cantidad',
                           title="Volumen de Pedidos por Fecha de Entrega",
                           labels={'fecha_entrega': 'Fecha', 'cantidad': 'Latas'})
            st.plotly_chart(fig2, use_container_width=True)
        
        # Tabla de últimos pedidos
        st.subheader("📋 Últimos Pedidos")
        ultimos_pedidos = df_pedidos.sort_values('id', ascending=False).head(10)
        st.dataframe(ultimos_pedidos[['numero', 'cliente_nombre', 'cantidad', 'fecha_entrega', 'lleva_rt']], use_container_width=True)
    else:
        st.info("No hay pedidos cargados. Ve a 'Cargar Pedido' para añadir.")

# ============================================
# 2. MÁQUINAS
# ============================================
elif menu == "🏭 Máquinas":
    st.header("🏭 Estado de Máquinas")
    
    if maquinas:
        for m in maquinas:
            with st.container():
                col1, col2, col3 = st.columns([2, 2, 1])
                with col1:
                    st.subheader(f"🖥️ {m.get('nombre', 'N/A')}")
                    st.caption(f"Formato: {m.get('formato', 'N/A')}")
                with col2:
                    st.metric("⚡ Velocidad", f"{m.get('velocidad', 0)} latas/min")
                    st.metric("📦 Capacidad", f"{m.get('capacidad', 0):,} latas/día")
                with col3:
                    # Simular carga (en producción se calcularía de pedidos reales)
                    carga = 65
                    st.progress(carga / 100)
                    st.caption(f"Carga: {carga}%")
                st.markdown("---")
    else:
        st.info("No hay máquinas registradas. Primero añade máquinas en Supabase.")

# ============================================
# 3. PLANIFICACIÓN (GANTT + PLANILLA)
# ============================================
elif menu == "📅 Planificación":
    st.header("📅 Planificación de Producción")
    
    if not pedidos:
        st.warning("⚠️ No hay pedidos para planificar. Ve a 'Cargar Pedido' para añadir pedidos.")
    else:
        # Controles
        col1, col2 = st.columns([2, 1])
        with col1:
            fecha_inicio = st.date_input("Fecha de inicio de planificación", datetime.now())
        with col2:
            dias = st.selectbox("Horizonte (días)", [5, 7, 10, 14], index=1)
        
        if st.button("🔄 Generar Planificación", type="primary", use_container_width=True):
            with st.spinner("Generando planificación..."):
                plan, saturacion, cargas_totales, cargas_diarias = generar_planificacion(pedidos, fecha_inicio, dias)
            
            # Gráfico de saturación
            st.subheader("📊 Saturación de Máquinas")
            df_sat = pd.DataFrame([{"Máquina": k, "Saturación %": v} for k, v in saturacion.items()])
            fig_sat = px.bar(df_sat, x="Máquina", y="Saturación %", 
                            text="Saturación %", color="Saturación %",
                            color_continuous_scale=["green", "yellow", "red"],
                            title="Carga de trabajo semanal por máquina")
            fig_sat.update_traces(textposition='outside')
            st.plotly_chart(fig_sat, use_container_width=True)
            
            # Diagrama de Gantt
            st.subheader("📊 Diagrama de Gantt - Distribución por Máquina y Día")
            mostrar_gantt(plan, fecha_inicio, dias)
            
            # Planilla semanal
            mostrar_planilla_semanal(plan, fecha_inicio, dias, saturacion)
            
            # Resumen de cargas
            st.subheader("📊 Resumen de Producción por Máquina")
            cols = st.columns(5)
            for i, (maq, carga) in enumerate(cargas_totales.items()):
                with cols[i]:
                    st.metric(maq, f"{carga:,} latas", f"{saturacion.get(maq, 0)}%")

# ============================================
# 4. PEDIDOS - LISTADO
# ============================================
elif menu == "📦 Pedidos":
    st.header("📦 Gestión de Pedidos")
    
    if pedidos:
        df_pedidos = pd.DataFrame(pedidos)
        
        # Estadísticas
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Pedidos", len(pedidos))
        with col2:
            st.metric("Total Latas", f"{df_pedidos['cantidad'].sum():,}")
        with col3:
            st.metric("Pedidos con RT", df_pedidos['lleva_rt'].sum())
        
        st.markdown("---")
        
        # Tabla de pedidos
        st.dataframe(df_pedidos[['numero', 'cliente_nombre', 'cantidad', 'fecha_entrega', 'lleva_rt']], use_container_width=True)
        
        # Botón para eliminar (con confirmación)
        st.subheader("🗑️ Eliminar Pedido")
        pedido_a_eliminar = st.selectbox("Seleccionar pedido a eliminar", [p['numero'] for p in pedidos])
        if st.button("Eliminar Pedido", type="secondary"):
            for p in pedidos:
                if p['numero'] == pedido_a_eliminar:
                    if delete_data("pedidos", "id", p['id']):
                        st.success(f"Pedido {pedido_a_eliminar} eliminado")
                        st.rerun()
                    break
    else:
        st.info("No hay pedidos registrados. Ve a 'Cargar Pedido' para añadir.")

# ============================================
# 5. CARGAR PEDIDO
# ============================================
elif menu == "📄 Cargar Pedido":
    st.header("📄 Cargar Nuevo Pedido")
    
    st.info("📝 Copia y pega el texto del pedido en el cuadro de abajo")
    
    with st.expander("📋 Ver ejemplo de formato aceptado"):
        st.code("""
1000895661880 RR-120 LULAS DE CALDEIRADA S/E 56.000 1 56.000
1000895561883 RR-120 LULAS RECHEADAS CALDEIRADA S/E 35.532 1 35.532
1000898461845 RR-120 POTA GIGANTE EM CALDEIRADA S/E 23.688 1 23.688
5603344651041 RR-120 LULAS DE CALDEIRADA RT10 GENERAL 220 100 22.000
        """)
    
    texto_pedido = st.text_area("Texto del pedido:", height=200)
    
    if st.button("🔍 Procesar Pedido", type="primary", use_container_width=True):
        if texto_pedido:
            with st.spinner("Procesando líneas..."):
                lineas = extraer_lineas(texto_pedido)
            
            if lineas:
                st.success(f"✅ Se encontraron {len(lineas)} líneas")
                st.dataframe(pd.DataFrame(lineas), use_container_width=True)
                
                total_latas = sum(l['cantidad'] for l in lineas)
                st.metric("📦 Total latas del pedido", f"{total_latas:,}")
                
                # Datos del pedido
                st.subheader("📝 Datos del pedido")
                col1, col2 = st.columns(2)
                with col1:
                    pedido_numero = st.text_input("Número de pedido", "PEDIDO_NUEVO")
                    fecha_entrega = st.date_input("Fecha de entrega", datetime.now() + timedelta(days=7))
                with col2:
                    if clientes:
                        opciones = [c['nombre'] for c in clientes]
                        cliente = st.selectbox("Cliente", opciones)
                    else:
                        st.warning("No hay clientes. Ve a Supabase y añade clientes a la tabla 'clientes'")
                        cliente = "CLIENTE_TEST"
                
                if st.button("💾 Guardar Pedido", type="primary", use_container_width=True):
                    # Obtener ID del cliente
                    cliente_id = 1
                    for c in clientes:
                        if c['nombre'] == cliente:
                            cliente_id = c['id']
                            break
                    
                    # Guardar cada línea como un pedido separado
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
