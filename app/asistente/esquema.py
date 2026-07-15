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
articulo_precios(id, articulo_id -> articulos.id, lista_id -> listas_precio.id,
                 precio numeric, margen numeric)
  -- precio de venta de cada artículo por lista.

proveedores(id, codigo, razon_social, cuit, telefono, email, activo boolean)
articulo_proveedores(id, articulo_id -> articulos.id, proveedor_id -> proveedores.id,
                     codigo_proveedor, costo numeric, es_preferido boolean)

clientes(id, codigo, denominacion, cuit, cond_fiscal, limite_cta_cte numeric,
         telefono, email, direccion, activo boolean)
  -- limite_cta_cte = límite de crédito. La DEUDA de cuenta corriente todavía NO existe en el
  --   sistema (es una fase futura): si te preguntan por deuda/saldo, aclará que no está disponible.

vehiculos(id, marca, modelo, anio_desde, anio_hasta, motor, version)
articulo_aplicaciones(id, articulo_id -> articulos.id, vehiculo_id -> vehiculos.id,
                      origen, confirmado boolean, nota)
  -- qué repuesto sirve para qué vehículo. confirmado=false son sugerencias sin validar.

depositos(id, codigo, nombre)
stock(org_id, articulo_id, deposito_id, cantidad numeric)
  -- VISTA de solo lectura: stock actual por artículo y depósito. Para stock total de un artículo,
  --   sumá cantidad agrupando por articulo_id. Artículos "bajo punto de pedido" = el stock total
  --   es <= articulos.punto_pedido.
"""
