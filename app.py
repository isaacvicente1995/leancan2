import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
import re
import plotly.express as px
import time

st.set_page_config(page_title="LeanCan", page_icon="🏭", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #f0f2f6; }
    h1 { color: #1a365d !important; border-bottom: 3px solid #2c5282 !important; }
    .metric-card { background: linear-gradient(135deg, #1e3a5f 0%, #2c5282 100%); border-radius: 12px; padding: 20px; color: white; }
    .machine-card { background: white; border-radius: 10px; padding: 15px; margin: 10px 0; border-left: 4px solid #2c5282; }
    .config-card { background: #f7f9fc; border-radius: 10px; padding: 15px; margin: 10px 0; border: 1px solid #e2e8f0; }
    .stButton > button { background-color: #2c5282; color: white; }
    .small-text { font-size: 12px; color: #718096; }
    .speed-table { font-size: 12px; }
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

def supabase_get(table, filters=None):
    url = f"{SUPABASE_URL}/{table}"
    if filters:
        url += f"?{filters}"
    try:
        response = requests.get(url, headers=HEADERS)
        if response.status_code == 200:
            return response.json()
        return []
    except:
        return []

def supabase_post(table, data):
    try:
        response = requests.post(f"{SUPABASE_URL}/{table}", headers=HEADERS, json=data)
        return response.status_code in [200, 201]
    except:
        return False

def supabase_put(table, id_field, id_value, data):
    try:
        response = requests.patch(f"{SUPABASE_URL}/{table}?{id_field}=eq.{id_value}", headers=HEADERS, json=data)
        return response.status_code in [200, 204]
    except:
        return False

def supabase_delete(table, id_field, id_value):
    try:
        response = requests.delete(f"{SUPABASE_URL}/{table}?{id_field}=eq.{id_value}", headers=HEADERS)
        return response.status_code == 204
    except:
        return False

# ============================================
# FUNCIONES DE CÁLCULO
# ============================================
def calcular_capacidad_diaria(velocidad, disponibilidad, oee):
    """Calcula capacidad diaria en latas"""
    minutos_totales = disponibilidad * 60
    capacidad_teorica = velocidad * minutos_totales
    capacidad_real = capacidad_teorica * (oee / 100)
    return int(capacidad_real)

def extraer_tipo_producto(sku, nombre):
    """Determina el tipo de producto basado en SKU o nombre"""
    if 'RT10' in nombre or 'RT' in nombre.upper():
        return ('RT', 'RT-10')
    elif 'RO-85' in nombre or 'PACK' in nombre:
        return ('RO-85', 'PACK6')
    else:
        return ('RR-120', 'CAJA25')

def extraer_lineas(texto):
    """Extrae productos del pedido"""
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
            nombre = linea.replace(sku_match.group(1), '').strip()
            nombre = re.sub(r'\s+', ' ', nombre)[:50]
            producto_tipo, caja_tipo = extraer_tipo_producto(sku_match.group(1), nombre)
            lineas.append({
                'sku': sku_match.group(1),
                'nombre': nombre,
                'cantidad': cantidad,
                'lleva_rt': lleva_rt,
                'producto_tipo': producto_tipo,
                'caja_tipo': caja_tipo
            })
    return lineas

def obtener_todas_velocidades():
    """Obtiene todas las configuraciones de máquinas"""
    return supabase_get("maquinas_velocidades")

def actualizar_velocidad(id_registro, nueva_velocidad):
    """Actualiza la velocidad de un registro"""
    return supabase_put("maquinas_velocidades", "id", id_registro, {"velocidad": nueva_velocidad})

def actualizar_oee_disponibilidad(equipo, nuevo_oee, nueva_disponibilidad):
    """Actualiza OEE y disponibilidad para todas las velocidades de un equipo"""
    registros = supabase_get("maquinas_velocidades", f"equipo=eq.{equipo}")
    for reg in registros:
        supabase_put("maquinas_velocidades", "id", reg['id'], {
            "oee": nuevo_oee,
            "disponibilidad": nueva_disponibilidad
        })

def asignar_maquinas_inteligente(lineas_pedido, velocidades_config):
    """Asigna productos a máquinas según velocidades específicas"""
    equipos = ['E1', 'E2', 'E3', 'E5', 'E8']
    capacidad_equipo = {}
    carga_equipo = {e: 0 for e in equipos}
    asignaciones = []
    
    # Agrupar velocidades por equipo
    velocidades_por_equipo = {}
    for v in velocidades_config:
        equipo = v['equipo']
        if equipo not in velocidades_por_equipo:
            velocidades_por_equipo[equipo] = []
        velocidades_por_equipo[equipo].append(v)
    
    # Calcular capacidad por equipo
    for e in equipos:
        if e in velocidades_por_equipo and velocidades_por_equipo[e]:
            vel_max = max(v['velocidad'] for v in velocidades_por_equipo[e])
            oee = velocidades_por_equipo[e][0].get('oee', 60)
            disp = velocidades_por_equipo[e][0].get('disponibilidad', 7.5)
            capacidad_equipo[e] = calcular_capacidad_diaria(vel_max, disp, oee)
        else:
            capacidad_equipo[e] = 30000
    
    for linea in lineas_pedido:
        cantidad = linea['cantidad']
        producto_tipo = linea['producto_tipo']
        caja_tipo = linea['caja_tipo']
        lleva_rt = linea['lleva_rt']
        
        # Encontrar máquinas que pueden producir este producto
        maquinas_posibles = []
        for e in equipos:
            if e in velocidades_por_equipo:
                for v in velocidades_por_equipo[e]:
                    if v['producto_tipo'] == producto_tipo and v['caja_tipo'] == caja_tipo:
                        maquinas_posibles.append(e)
                        break
        
        if not maquinas_posibles:
            maquinas_posibles = ['E2'] if not lleva_rt else ['E5']
        
        # Elegir máquina con menos carga relativa
        mejor_maquina = min(maquinas_posibles, 
                           key=lambda m: carga_equipo[m] / capacidad_equipo[m] if capacidad_equipo[m] > 0 else 0)
        
        asignaciones.append({
            'sku': linea['sku'],
            'nombre': linea['nombre'],
            'cantidad': cantidad,
            'maquina': mejor_maquina,
            'producto_tipo': producto_tipo,
            'caja_tipo': caja_tipo,
            'lleva_rt': lleva_rt
        })
        carga_equipo[mejor_maquina] += cantidad
    
    # Calcular porcentajes
    porcentajes = {}
    for e in equipos:
        porcentajes[e] = round((carga_equipo[e] / capacidad_equipo[e]) * 100, 1) if capacidad_equipo[e] > 0 else 0
    
    return asignaciones, carga_equipo, porcentajes, capacidad_equipo

# ============================================
# CARGA DE DATOS
# ============================================
with st.spinner("🔄 Cargando datos..."):
    clientes = supabase_get("clientes")
    pedidos = supabase_get("pedidos")
    lineas_pedido = supabase_get("lineas_pedido")
    todas_velocidades = obtener_todas_velocidades()

# ============================================
# MENÚ (NUEVO ORDEN)
# ============================================
st.sidebar.markdown("<h2 style='text-align: center;'>🏭 LeanCan</h2>", unsafe_allow_html=True)
menu = st.sidebar.radio("", [
    "📊 PANEL", 
    "📦 PEDIDOS", 
    "📄 IMPORTAR", 
    "📅 PLANIFICACIÓN", 
    "⚙️ CONFIGURACIÓN MÁQUINAS"
])

# ============================================
# 1. PANEL
# ============================================
if menu == "📊 PANEL":
    st.markdown("<h1>Panel de Control</h1>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns(3)
    col1.metric("📦 Pedidos", len(pedidos))
    col2.metric("📋 Productos", len(lineas_pedido))
    col3.metric("🥫 Latas", sum(l.get('cantidad', 0) for l in lineas_pedido))
    
    if pedidos:
        st.subheader("Últimos pedidos")
        st.dataframe(pd.DataFrame(pedidos[-5:]), use_container_width=True)

# ============================================
# 2. PEDIDOS
# ============================================
elif menu == "📦 PEDIDOS":
    st.markdown("<h1>Pedidos</h1>", unsafe_allow_html=True)
    
    if pedidos:
        df_ped = pd.DataFrame(pedidos)
        st.dataframe(df_ped[['id', 'numero', 'cliente_id', 'fecha_entrega', 'estado']], use_container_width=True)
        
        if lineas_pedido:
            st.subheader("📋 Productos por Pedido")
            df_lineas = pd.DataFrame(lineas_pedido)
            st.dataframe(df_lineas[['pedido_id', 'sku', 'nombre', 'cantidad', 'lleva_rt']], use_container_width=True)
    else:
        st.info("No hay pedidos registrados")

# ============================================
# 3. IMPORTAR PEDIDO
# ============================================
elif menu == "📄 IMPORTAR":
    st.markdown("<h1>Importar Pedido</h1>", unsafe_allow_html=True)
    
    with st.expander("📋 Ejemplo - Copia este texto"):
        st.code("""
1000895661880 RR-120 LULAS DE CALDEIRADA S/E 56.000 1 56.000
1000895561883 RR-120 LULAS RECHEADAS CALDEIRADA S/E 35.532 1 35.532
5603344651041 RR-120 LULAS DE CALDEIRADA RT10 GENERAL 220 100 22.000
        """)
    
    texto_pedido = st.text_area("📝 Pega aquí el texto del pedido completo:", height=200)
    
    col1, col2 = st.columns(2)
    with col1:
        pedido_numero = st.text_input("Número de pedido", "PED_" + datetime.now().strftime("%Y%m%d%H%M%S"))
        fecha_entrega = st.date_input("Fecha de entrega", datetime.now() + timedelta(days=7))
    with col2:
        opciones = [c['nombre'] for c in clientes] if clientes else ["CLIENTE_TEST"]
        cliente = st.selectbox("Cliente", opciones)
    
    if st.button("📥 IMPORTAR PEDIDO", type="primary", use_container_width=True):
        if texto_pedido:
            with st.spinner("Procesando..."):
                lineas = extraer_lineas(texto_pedido)
            
            if lineas:
                st.success(f"✅ {len(lineas)} productos extraídos")
                
                cliente_id = None
                for c in clientes:
                    if c['nombre'] == cliente:
                        cliente_id = c['id']
                        break
                
                if cliente_id is None:
                    st.error("❌ Cliente no encontrado")
                else:
                    pedido_data = {
                        "numero": pedido_numero,
                        "cliente_id": cliente_id,
                        "fecha_entrega": str(fecha_entrega),
                        "estado": "pendiente"
                    }
                    
                    if supabase_post("pedidos", pedido_data):
                        pedidos_actualizados = supabase_get("pedidos")
                        pedido_id = None
                        for p in pedidos_actualizados:
                            if p['numero'] == pedido_numero:
                                pedido_id = p['id']
                                break
                        
                        if pedido_id:
                            for item in lineas:
                                linea_data = {
                                    "pedido_id": pedido_id,
                                    "sku": item['sku'],
                                    "nombre": item['nombre'],
                                    "cantidad": item['cantidad'],
                                    "lleva_rt": 1 if item['lleva_rt'] else 0
                                }
                                supabase_post("lineas_pedido", linea_data)
                            
                            st.success(f"✅ Pedido {pedido_numero} guardado con {len(lineas)} productos")
                            st.balloons()
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error("No se pudo obtener el ID del pedido")
                    else:
                        st.error("Error al guardar el pedido")
            else:
                st.error("No se encontraron productos")
        else:
            st.warning("Pega el texto del pedido")

# ============================================
# 4. PLANIFICACIÓN
# ============================================
elif menu == "📅 PLANIFICACIÓN":
    st.markdown("<h1>Planificación de Producción</h1>", unsafe_allow_html=True)
    
    if not lineas_pedido:
        st.warning("⚠️ No hay productos cargados. Importa un pedido primero.")
    else:
        if st.button("🚀 RECALCULAR PLANIFICACIÓN", type="primary", use_container_width=True):
            with st.spinner("Distribuyendo productos entre máquinas según velocidades específicas..."):
                asignaciones, cargas, porcentajes, capacidades = asignar_maquinas_inteligente(lineas_pedido, todas_velocidades)
            
            st.success(f"✅ {len(asignaciones)} productos asignados")
            
            # Gráfico de carga
            st.subheader("📊 Carga por Máquina")
            df_carga = pd.DataFrame([
                {"Máquina": m, "Latas": cargas[m], "Capacidad": capacidades[m], "%": porcentajes[m]}
                for m in ['E1', 'E2', 'E3', 'E5', 'E8']
            ])
            fig = px.bar(df_carga, x="Máquina", y="%", text="%", color="%", 
                        color_continuous_scale=["green","yellow","red"])
            fig.update_traces(textposition='outside')
            st.plotly_chart(fig, use_container_width=True)
            
            # Tabla de asignaciones
            st.subheader("📋 Asignación por Máquina")
            for maquina in ['E1', 'E2', 'E3', 'E5', 'E8']:
                asig = [a for a in asignaciones if a['maquina'] == maquina]
                if asig:
                    with st.expander(f"🖥️ {maquina} - {cargas[maquina]:,} / {capacidades[maquina]:,} latas ({porcentajes[maquina]}%)"):
                        for a in asig:
                            rt = " (con RT)" if a['lleva_rt'] else ""
                            st.write(f"📦 {a['sku']} - {a['nombre'][:40]}: {a['cantidad']:,} latas{rt} | Tipo: {a['producto_tipo']}-{a['caja_tipo']}")

# ============================================
# 5. CONFIGURACIÓN MÁQUINAS (EDITAR TODO)
# ============================================
elif menu == "⚙️ CONFIGURACIÓN MÁQUINAS":
    st.markdown("<h1>Configuración de Máquinas</h1>", unsafe_allow_html=True)
    
    st.info("""
    **Aquí puedes modificar:**
    - Velocidades por producto (latas/min)
    - OEE (%) - Efectividad global del equipo
    - Disponibilidad (horas/día)
    """)
    
    if not todas_velocidades:
        st.warning("No hay configuración de máquinas. Ejecuta el SQL de inserción primero.")
    else:
        # Agrupar por equipo
        equipos_dict = {}
        for v in todas_velocidades:
            equipo = v['equipo']
            if equipo not in equipos_dict:
                equipos_dict[equipo] = []
            equipos_dict[equipo].append(v)
        
        # Editar OEE y Disponibilidad global por equipo
        st.subheader("📊 Parámetros Globales por Equipo")
        for equipo, configs in equipos_dict.items():
            with st.expander(f"⚙️ {equipo} - Parámetros Globales", expanded=False):
                oee_actual = configs[0].get('oee', 60)
                disp_actual = configs[0].get('disponibilidad', 7.5)
                
                col1, col2 = st.columns(2)
                with col1:
                    nuevo_oee = st.number_input(f"OEE (%) - {equipo}", value=oee_actual, step=5, min_value=0, max_value=100, key=f"oee_{equipo}")
                with col2:
                    nueva_disp = st.number_input(f"Disponibilidad (h/día) - {equipo}", value=disp_actual, step=0.5, min_value=0.0, max_value=24.0, key=f"disp_{equipo}")
                
                if st.button(f"💾 Guardar parámetros {equipo}", key=f"save_global_{equipo}"):
                    for reg in configs:
                        supabase_put("maquinas_velocidades", "id", reg['id'], {
                            "oee": nuevo_oee,
                            "disponibilidad": nueva_disp
                        })
                    st.success(f"✅ Parámetros de {equipo} actualizados")
                    time.sleep(0.5)
                    st.rerun()
        
        st.markdown("---")
        
        # Editar velocidades específicas por producto
        st.subheader("⚡ Velocidades por Producto")
        
        for equipo, configs in equipos_dict.items():
            with st.expander(f"🖥️ {equipo} - Velocidades por Producto", expanded=False):
                st.markdown(f"**Configuraciones actuales de {equipo}:**")
                
                for cfg in configs:
                    col1, col2, col3 = st.columns([3, 2, 1])
                    with col1:
                        st.write(f"📦 {cfg['producto_tipo']} - {cfg['caja_tipo']}")
                    with col2:
                        nueva_vel = st.number_input(
                            f"Velocidad (latas/min)", 
                            value=cfg['velocidad'], 
                            step=10, 
                            key=f"vel_{cfg['id']}"
                        )
                    with col3:
                        if st.button(f"💾", key=f"save_vel_{cfg['id']}"):
                            supabase_put("maquinas_velocidades", "id", cfg['id'], {"velocidad": nueva_vel})
                            st.success(f"✅ Velocidad actualizada")
                            time.sleep(0.3)
                            st.rerun()
                
                # Mostrar capacidades calculadas
                st.markdown("---")
                st.caption(f"**Capacidades calculadas con parámetros actuales:**")
                for cfg in configs:
                    vel = cfg['velocidad']
                    oee = cfg.get('oee', 60)
                    disp = cfg.get('disponibilidad', 7.5)
                    cap = calcular_capacidad_diaria(vel, disp, oee)
                    st.caption(f"  📊 {cfg['producto_tipo']}-{cfg['caja_tipo']}: {vel} latas/min → {cap:,} latas/día")
