from pydantic import BaseModel, ConfigDict, Field


class ProveedorLeer(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    codigo: str
    razon_social: str
    cuit: str | None
    telefono: str | None
    email: str | None
    activo: bool


class ProveedorPagina(BaseModel):
    """Una página del padrón + el total del resultado filtrado (para paginar en el front).

    Espeja `ClientePagina`. El `total` es el del resultado FILTRADO, no el del padrón entero.
    """

    items: list[ProveedorLeer]
    total: int


class ProveedorCrear(BaseModel):
    """Alta de proveedor desde la app.

    NO lleva `codigo`: lo genera el sistema (`service.generar_codigo`). El correlativo es del
    servidor, y aceptarlo por el body abriría la puerta a que dos personas elijan el mismo y se
    lleven un 409 evitable.

    Los `max_length` espejan el `String(n)` de la tabla: sin ellos un texto largo llega a Postgres
    y vuelve como `DataError` = 500, en vez de un 422 que dice qué campo se pasó.

    Sin `cond_fiscal` ni `limite_cta_cte`, a diferencia del cliente: a un proveedor no se le
    factura ni se le fija un límite de crédito — la deuda va para el otro lado.
    """

    razon_social: str = Field(min_length=1, max_length=120)
    cuit: str | None = Field(default=None, max_length=13)
    telefono: str | None = Field(default=None, max_length=40)
    email: str | None = Field(default=None, max_length=120)
