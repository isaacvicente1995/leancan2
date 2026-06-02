elif menu == "📄 Cargar Pedido":
    st.header("📄 Cargar Pedido")
    
    # Opción 1: Pegar texto (RECOMENDADO)
    st.subheader("📝 Opción 1: Pegar el texto del pedido")
    st.info("Copia y pega el contenido del pedido (desde el PDF o email)")
    
    texto_pedido = st.text_area("Texto del pedido:", height=250)
    
    if texto_pedido:
        # Parsear el texto
        lineas = []
        
        # Dividir por líneas
        for linea in texto_pedido.split('\n'):
            # Buscar SKU (código de 6-10 dígitos)
            import re
            sku_match = re.search(r'\b(\d{6,10})\b', linea)
            
            # Buscar cantidad (números grandes)
            cantidades = re.findall(r'\b(\d{1,3}(?:\.\d{3})*|\d{4,})\b', linea)
            cantidad = 0
            for c in cantidades:
                num = int(c.replace('.', ''))
                if num > 1000 and num < 1000000:
                    cantidad = num
                    break
            
            # Detectar RT
            lleva_rt = 'RT10' in linea or 'retractil' in linea.lower()
            
            # Detectar producto
            producto = linea.strip()
            if sku_match:
                sku = sku_match.group(1)
                # Limpiar el texto
                producto = producto.replace(sku, '').strip()
                
                if cantidad > 0:
                    lineas.append({
                        'sku': sku,
                        'producto': producto[:50],
                        'cantidad': cantidad,
                        'lleva_rt': lleva_rt
                    })
        
        if lineas:
            st.success(f"✅ Se encontraron {len(lineas)} líneas de pedido")
            
            # Mostrar líneas encontradas
            df_lineas = pd.DataFrame(lineas)
            st.dataframe(df_lineas, use_container_width=True)
            
            # Pedir datos del pedido
            col1, col2 = st.columns(2)
            with col1:
                pedido_numero = st.text_input("Número de pedido", "RAF2026/206")
                fecha_entrega = st.date_input("Fecha de entrega", datetime.now())
            with col2:
                cliente_opciones = [c['nombre'] for c in clientes_data] if clientes_data else ["RAMIREZ Y CIA"]
                cliente = st.selectbox("Cliente", cliente_opciones)
            
            # Separar en líneas de trabajo
            st.subheader("📋 Separación en Líneas de Trabajo")
            
            # Clasificar por máquina
            lineas_e1 = []
            lineas_e2 = []
            lineas_e3 = []
            lineas_e5 = []
            lineas_e8 = []
            
            for item in lineas:
                if item['lleva_rt']:
                    lineas_e5.append(item)
                else:
                    # Alternar entre E1 y E3 para balancear
                    if len(lineas_e1) <= len(lineas_e3):
                        lineas_e1.append(item)
                    else:
                        lineas_e3.append(item)
            
            # Mostrar propuesta
            col1, col2, col3, col4, col5 = st.columns(5)
            
            with col1:
                total_e1 = sum(l['cantidad'] for l in lineas_e1)
                st.metric("E1", f"{total_e1:,} latas")
                for l in lineas_e1:
                    st.caption(f"{l['sku']}: {l['cantidad']:,}")
            
            with col2:
                total_e2 = sum(l['cantidad'] for l in lineas_e2)
                st.metric("E2", f"{total_e2:,} latas")
                for l in lineas_e2:
                    st.caption(f"{l['sku']}: {l['cantidad']:,}")
            
            with col3:
                total_e3 = sum(l['cantidad'] for l in lineas_e3)
                st.metric("E3", f"{total_e3:,} latas")
                for l in lineas_e3:
                    st.caption(f"{l['sku']}: {l['cantidad']:,}")
            
            with col4:
                total_e5 = sum(l['cantidad'] for l in lineas_e5)
                st.metric("E5 (RT)", f"{total_e5:,} latas")
                for l in lineas_e5:
                    st.caption(f"{l['sku']}: {l['cantidad']:,}")
            
            with col5:
                total_e8 = sum(l['cantidad'] for l in lineas_e8)
                st.metric("E8", f"{total_e8:,} latas")
            
            # Botón para guardar
            if st.button("💾 Guardar Pedido en Base de Datos", type="primary"):
                # Obtener cliente_id
                cliente_id = 1
                for c in clientes_data:
                    if c['nombre'] == cliente:
                        cliente_id = c['id']
                        break
                
                # Guardar cada línea
                for item in lineas:
                    insert_data("pedidos", {
                        "numero": pedido_numero,
                        "cliente_id": cliente_id,
                        "fecha_entrega": str(fecha_entrega),
                        "cantidad": item['cantidad'],
                        "producto_sku": item['sku'],
                        "lleva_rt": 1 if item['lleva_rt'] else 0
                    })
                
                st.success(f"✅ Pedido {pedido_numero} guardado con {len(lineas)} líneas")
                
                # Mostrar resumen
                st.subheader("📊 Resumen de Producción")
                st.write(f"**Total latas:** {sum(l['cantidad'] for l in lineas):,}")
                st.write(f"**Con RT:** {sum(1 for l in lineas if l['lleva_rt'])} líneas - {sum(l['cantidad'] for l in lineas if l['lleva_rt']):,} latas → E5")
                st.write(f"**Sin RT:** {sum(1 for l in lineas if not l['lleva_rt'])} líneas - {sum(l['cantidad'] for l in lineas if not l['lleva_rt']):,} latas → E1/E3")
    
    # Opción 2: Subir archivo (limitado)
    st.subheader("📎 Opción 2: Subir archivo (CSV o Excel)")
    st.caption("Solo archivos CSV o Excel. Para PDF, usa la Opción 1 y copia el texto.")
    
    archivo = st.file_uploader("Seleccionar archivo", type=['csv', 'xlsx'])
    
    if archivo:
        try:
            if archivo.name.endswith('.csv'):
                df = pd.read_csv(archivo)
            else:
                df = pd.read_excel(archivo)
            
            st.dataframe(df, use_container_width=True)
            
            if st.button("Guardar desde archivo"):
                for _, row in df.iterrows():
                    insert_data("pedidos", {
                        "numero": "IMPORTED",
                        "cliente_id": 1,
                        "fecha_entrega": str(datetime.now().date()),
                        "cantidad": int(row.iloc[0]) if pd.notna(row.iloc[0]) else 0,
                        "producto_sku": str(row.iloc[1]) if len(row) > 1 else "UNKNOWN",
                        "lleva_rt": 0
                    })
                st.success("Pedidos importados")
        except Exception as e:
            st.error(f"Error al leer archivo: {e}")
