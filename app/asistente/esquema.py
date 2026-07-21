"""Descripción CURADA del esquema que ve el LLM para generar SQL.

NO es el DDL completo. A propósito expone solo la superficie de LECTURA del negocio y OMITE las
tablas de auth (`organizaciones`, `miembros`) y las columnas internas (`embedding`, `busqueda`).
El LLM no puede consultar lo que no conoce, y el rol read-only + RLS son la reja dura por si igual
lo intenta.

Importante para el prompt: el tenant YA está fijado por RLS a nivel de conexión. El LLM NO tiene
que —ni puede— filtrar por `org_id`: cada query ve solo los datos de la organización del usuario.
"""

ESQUEMA = """\
Tablas disponibles (PostgreSQL). Todas están ya filtradas por organización vía RLS: NO agregues
condiciones por org_id, no existe para vos.

articulos(id, codigo, detalle, costo numeric, alicuota_iva numeric, punto_pedido numeric,
          marca, rubro, codigo_barra, activo boolean)
  -- catálogo de repuestos. costo es el costo de compra. punto_pedido = umbral de reposición.

listas_precio(id, codigo, nombre)
  -- nombre lleva el prefijo 'Lista ' (ej: codigo 'MOST' -> nombre 'Lista Mostrador'). Para
  --   filtrar por lista preferí codigo, o usá ILIKE sobre nombre ('%mostrador%').
articulo_precios(id, articulo_id -> articulos.id, lista_id -> listas_precio.id,
                 precio numeric, margen numeric)
  -- precio de venta de cada artículo por lista.

proveedores(id, codigo, razon_social, cuit, telefono, email, activo boolean)
articulo_proveedores(id, articulo_id -> articulos.id, proveedor_id -> proveedores.id,
                     codigo_proveedor, costo numeric, es_preferido boolean)

clientes(id, codigo, denominacion, cuit, cond_fiscal, limite_cta_cte numeric,
         telefono, email, direccion, activo boolean)
  -- limite_cta_cte = límite de crédito. La DEUDA actual del cliente está en la vista
  --   cliente_saldo (columna saldo), no acá.

vehiculos(id, marca, modelo, anio_desde, anio_hasta, motor, version)
articulo_aplicaciones(id, articulo_id -> articulos.id, vehiculo_id -> vehiculos.id,
                      origen, confirmado boolean, nota)
  -- qué repuesto sirve para qué vehículo. confirmado=false son sugerencias sin validar.

depositos(id, codigo, nombre)
stock(org_id, articulo_id, deposito_id, cantidad numeric)
  -- VISTA de solo lectura: stock actual por artículo y depósito. Para stock total de un artículo,
  --   sumá cantidad agrupando por articulo_id. Artículos "bajo punto de pedido" = el stock total
  --   es <= articulos.punto_pedido.

comprobantes(id, cliente_id -> clientes.id, deposito_id -> depositos.id, tipo, pto_venta,
             numero, fecha date, condicion, neto numeric, iva numeric, total numeric)
  -- cada VENTA. tipo es 'FAC'/'PRE'/etc; condicion es 'contado' o 'cta_cte'; fecha es la fecha de
  --   emisión; total = neto + iva. "Ventas de hoy" = sumá total where fecha = current_date. Un
  --   cliente "compró" si tiene comprobantes; su "última compra" = max(fecha) de los suyos; los
  --   "frecuentes" = los que más comprobantes tienen. "No compraron" = clientes sin comprobantes
  --   (left join clientes ... where comprobantes.id is null).

comprobante_items(id, comprobante_id -> comprobantes.id, articulo_id -> articulos.id,
                  cantidad numeric, precio_unitario numeric, alicuota_iva numeric,
                  importe_iva numeric, total_renglon numeric)
  -- los renglones de cada comprobante. Para "lo más vendido" sumá cantidad agrupando por
  --   articulo_id. precio_unitario es neto (sin IVA).

cta_cte_movimientos(id, cliente_id -> clientes.id, fecha date, tipo, debe numeric, haber numeric)
  -- libro mayor de cuenta corriente: una venta a crédito es un 'debe', una cobranza un 'haber'.
  --   Para el SALDO de un cliente NO sumes acá a mano: usá la vista cliente_saldo.

cliente_saldo(org_id, cliente_id, saldo numeric)
  -- VISTA: saldo de cuenta corriente por cliente = suma(debe) - suma(haber). saldo > 0 = el
  --   cliente debe esa plata. Un cliente sin movimientos no aparece (su saldo es 0).
"""
