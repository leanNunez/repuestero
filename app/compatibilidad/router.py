from fastapi import APIRouter, Depends, Query

from app.catalogo.schemas import ArticuloLeer
from app.compatibilidad import service
from app.core.rls import TenantContext, get_tenant

router = APIRouter(prefix="/compatibilidad", tags=["compatibilidad"])


@router.get("/repuestos", response_model=list[ArticuloLeer])
def repuestos_para(
    marca: str = Query(max_length=40),
    modelo: str = Query(max_length=60),
    anio: int | None = Query(default=None, ge=1950, le=2100),
    solo_confirmados: bool = Query(default=False),
    tenant: TenantContext = Depends(get_tenant),
) -> list[ArticuloLeer]:
    """ "¿Tenés el filtro de aceite para un Gol Trend 2015?" — en una llamada."""
    vehiculos = service.buscar_vehiculo(
        tenant.session, tenant.org_id, marca=marca, modelo=modelo, anio=anio
    )

    vistos: dict[int, ArticuloLeer] = {}
    for vehiculo in vehiculos:
        for articulo in service.repuestos_para_vehiculo(
            tenant.session,
            tenant.org_id,
            vehiculo_id=vehiculo.id,
            solo_confirmados=solo_confirmados,
        ):
            vistos[articulo.id] = ArticuloLeer.model_validate(articulo)

    return list(vistos.values())
