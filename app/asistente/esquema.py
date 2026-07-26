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

cta_cte_movimientos(id, cliente_id -> clientes.id, fecha date, tipo, debe numeric, haber numeric,
                    ref_tipo, ref_id)
  -- libro mayor de cuenta corriente de CLIENTES: una venta a crédito es un 'debe', una cobranza
  --   un 'haber'. tipo es 'venta'|'cobranza'|'nota_credito'|'ajuste'. ref_tipo/ref_id apuntan al
  --   documento que lo generó ('comprobante' + comprobantes.id, 'nota_credito', 'recibo' +
  --   recibos.id). Las cobranzas ANTERIORES a julio 2026 los tienen vacíos: se registraban sin
  --   recibo. Para el SALDO de un cliente NO sumes acá a mano: usá la vista cliente_saldo.

recibos(id, cliente_id -> clientes.id, tipo, pto_venta, numero, fecha date, total numeric)
  -- el COMPROBANTE de cada cobro a un cliente. tipo es siempre 'REC' y numero es correlativo por
  --   punto de venta. El movimiento de cuenta corriente que generó apunta acá
  --   (cta_cte_movimientos.ref_tipo = 'recibo'). "Cobranzas de hoy" = sumá total where
  --   fecha = current_date. Un recibo no se anula ni se edita: si el cobro estuvo mal, hay un
  --   movimiento de ajuste que lo revierte.

recibo_formas_pago(id, recibo_id -> recibos.id, forma, monto numeric)
  -- con qué se cobró cada recibo: 'efectivo', 'cheque', 'transferencia' o 'tarjeta'. Un recibo
  --   puede tener VARIOS renglones (pago mixto), y sus montos suman el total del recibo. Para
  --   "cuánto entró en efectivo" sumá monto where forma = 'efectivo'.

cliente_saldo(org_id, cliente_id, saldo numeric)
  -- VISTA: saldo de cuenta corriente por cliente = suma(debe) - suma(haber). saldo > 0 = el
  --   cliente debe esa plata. Un cliente sin movimientos no aparece (su saldo es 0), así que para
  --   listar clientes con y sin deuda usá left join desde clientes.

compras(id, proveedor_id -> proveedores.id, deposito_id -> depositos.id, numero_comprobante,
        fecha date, condicion, neto numeric, iva numeric, total numeric)
  -- cada COMPRA a un proveedor: la contraparte de comprobantes del otro lado del mostrador.
  --   numero_comprobante es el número de la factura DEL PROVEEDOR, no un correlativo nuestro.
  --   condicion es 'contado' o 'cta_cte'. "Lo que le compré a X" = compras de ese proveedor.

compra_items(id, compra_id -> compras.id, articulo_id -> articulos.id, cantidad numeric,
             costo_unitario numeric, alicuota_iva numeric, importe_iva numeric,
             total_renglon numeric)
  -- los renglones de cada compra. costo_unitario es neto (sin IVA).

prov_cta_cte_movimientos(id, proveedor_id -> proveedores.id, fecha date, tipo, debe numeric,
                         haber numeric, ref_tipo, ref_id)
  -- libro mayor de cuenta corriente de PROVEEDORES: una compra a crédito es un 'debe', un pago
  --   un 'haber'. tipo es 'compra'|'pago'|'ajuste'. Mismo criterio que el de clientes, pero al
  --   revés: acá el saldo es lo que NOSOTROS debemos.

proveedor_saldo(org_id, proveedor_id, saldo numeric)
  -- VISTA: saldo por proveedor = suma(debe) - suma(haber). saldo > 0 = LE DEBEMOS esa plata a
  --   ese proveedor. Un proveedor sin movimientos no aparece (su saldo es 0).
  --   Ojo con la dirección: cliente_saldo es plata que nos deben, proveedor_saldo es plata que
  --   debemos. "¿A quién le debo?" se responde con esta vista, no con cliente_saldo.
"""
