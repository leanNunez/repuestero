from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy.orm import Session

from app.catalogo import service as catalogo_service
from app.catalogo.schemas import ArticuloCrear, ListaPrecioCrear
from app.clientes import service as clientes_service
from app.compatibilidad import service as compat_service
from app.importador.readers.base import SourceReader
from app.inventario import service as inventario_service
from app.proveedores import service as proveedores_service


@dataclass
class Resumen:
    contadores: dict[str, int] = field(default_factory=dict)

    def suma(self, clave: str, n: int = 1) -> None:
        self.contadores[clave] = self.contadores.get(clave, 0) + n

    def __str__(self) -> str:
        return "\n".join(f"  {k:<24} {v:>6}" for k, v in sorted(self.contadores.items()))


def importar(session: Session, org_id: UUID, reader: SourceReader) -> Resumen:
    """Carga un origen completo dentro de UNA organización.

    Persiste SIEMPRE a través de la capa `service`, nunca con INSERT crudo. No es
    ceremonia: significa que el importador pasa por las mismas validaciones que la app
    (CUIT con dígito verificador, motivos de stock válidos, la IA no puede auto-confirmar
    compatibilidad). Si importáramos con INSERT directo, el importador sería el agujero
    por donde entra la basura que después rompe todo lo demás.

    El `org_id` se pasa explícito a cada service: los datos importados quedan encerrados en
    su tenant desde el primer INSERT.
    """
    resumen = Resumen()

    listas = {}
    for codigo, nombre in reader.listas_precio():
        listas[codigo] = catalogo_service.crear_lista_precio(
            session, org_id, ListaPrecioCrear(codigo=codigo, nombre=nombre)
        )
        resumen.suma("listas_precio")

    depositos = {}
    for codigo, nombre in reader.depositos():
        depositos[codigo] = inventario_service.crear_deposito(
            session, org_id, codigo=codigo, nombre=nombre
        )
        resumen.suma("depositos")

    articulos = {}
    for raw in reader.articulos():
        articulos[raw.codigo] = catalogo_service.crear_articulo(
            session,
            org_id,
            ArticuloCrear(
                codigo=raw.codigo,
                detalle=raw.detalle,
                costo=raw.costo,
                alicuota_iva=raw.alicuota_iva,
                punto_pedido=raw.punto_pedido,
                marca=raw.marca,
                rubro=raw.rubro,
                codigo_barra=raw.codigo_barra,
            ),
        )
        resumen.suma("articulos")

    for raw in reader.precios():
        catalogo_service.fijar_precio(
            session,
            org_id,
            articulo=articulos[raw.articulo_codigo],
            lista=listas[raw.lista_codigo],
            precio=raw.precio,
            margen=raw.margen,
        )
        resumen.suma("precios")

    proveedores = {}
    for raw in reader.proveedores():
        proveedores[raw.codigo] = proveedores_service.crear_proveedor(
            session,
            org_id,
            codigo=raw.codigo,
            razon_social=raw.razon_social,
            cuit=raw.cuit,
            telefono=raw.telefono,
            email=raw.email,
        )
        resumen.suma("proveedores")

    for raw in reader.articulo_proveedores():
        proveedores_service.vincular_articulo(
            session,
            org_id,
            articulo_id=articulos[raw.articulo_codigo].id,
            proveedor_id=proveedores[raw.proveedor_codigo].id,
            codigo_proveedor=raw.codigo_proveedor,
            costo=raw.costo,
            es_preferido=raw.es_preferido,
        )
        resumen.suma("articulo_proveedores")

    for raw in reader.clientes():
        clientes_service.crear_cliente(
            session,
            org_id,
            codigo=raw.codigo,
            denominacion=raw.denominacion,
            cuit=raw.cuit,
            cond_fiscal=raw.cond_fiscal,
            limite_cta_cte=raw.limite_cta_cte,
            telefono=raw.telefono,
            email=raw.email,
            direccion=raw.direccion,
        )
        resumen.suma("clientes")

    vehiculos = {}
    for raw in reader.vehiculos():
        clave = (raw.marca, raw.modelo, raw.anio_desde, raw.anio_hasta)
        vehiculos[clave] = compat_service.crear_vehiculo(
            session,
            org_id,
            marca=raw.marca,
            modelo=raw.modelo,
            anio_desde=raw.anio_desde,
            anio_hasta=raw.anio_hasta,
            motor=raw.motor,
            version=raw.version,
        )
        resumen.suma("vehiculos")

    for raw in reader.aplicaciones():
        clave = (
            raw.vehiculo_marca,
            raw.vehiculo_modelo,
            raw.vehiculo_anio_desde,
            raw.vehiculo_anio_hasta,
        )
        compat_service.declarar_aplicacion(
            session,
            org_id,
            articulo_id=articulos[raw.articulo_codigo].id,
            vehiculo_id=vehiculos[clave].id,
            origen=raw.origen,
            confirmado=raw.confirmado,
            nota=raw.nota,
        )
        resumen.suma("aplicaciones")

    # El stock inicial entra como MOVIMIENTO de kardex, no como un número puesto a mano.
    # Desde la primera fila el stock es la suma de su historia. No hay otra forma de tocarlo.
    for raw in reader.stock_inicial():
        inventario_service.registrar_movimiento(
            session,
            org_id,
            articulo_id=articulos[raw.articulo_codigo].id,
            deposito_id=depositos[raw.deposito_codigo].id,
            cantidad=raw.cantidad,
            motivo="inicial",
            ref_tipo="importacion",
        )
        resumen.suma("stock_movimientos")

    return resumen
