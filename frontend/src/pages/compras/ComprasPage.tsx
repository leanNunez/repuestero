import { useReducer } from "react";

import type { ArticuloItem } from "@/entities/articulo/schema";
import { pesos } from "@/entities/remito/formato";
import { ESTADO_INICIAL, puedeEmitir, reducer, totales } from "@/features/compras/model/estado";
import { useCompras, useEmitirCompra } from "@/features/compras/model/hooks";
import { ListadoCompras } from "@/features/compras/ui/ListadoCompras";
import { RenglonCompraRow } from "@/features/compras/ui/RenglonCompraRow";
import { ResumenCompra } from "@/features/compras/ui/ResumenCompra";
import { SelectorProveedor } from "@/features/compras/ui/SelectorProveedor";
import { BuscadorArticulo } from "@/features/ventas/ui/BuscadorArticulo";
import { Button } from "@/shared/ui/button";
import { Card } from "@/shared/ui/card";
import { Field, FieldLabel } from "@/shared/ui/field";
import { Input } from "@/shared/ui/input";
import { SuccessPanel } from "@/shared/ui/success-panel";

export function ComprasPage() {
  const [estado, dispatch] = useReducer(reducer, ESTADO_INICIAL);
  const emitir = useEmitirCompra();
  const compras = useCompras();

  function onAgregar(a: ArticuloItem) {
    // El costo lo tipea el operador desde la factura del proveedor (no hay costo sugerido).
    dispatch({
      type: "agregar",
      renglon: {
        articulo_codigo: a.codigo,
        detalle: a.detalle,
        cantidad: "1",
        costo_unitario: "",
        alicuota_iva: a.alicuota_iva,
      },
    });
  }

  if (estado.paso === "listo" && emitir.data) {
    const r = emitir.data;
    return (
      <div className="mx-auto max-w-lg p-4 py-10 sm:p-6">
        <SuccessPanel>
          <div>
            <h1 className="text-lg font-semibold">Compra registrada</h1>
            <p className="mt-1 text-sm text-muted-foreground">
              Comprobante {r.numero_comprobante} · Total {pesos(r.total)}
            </p>
          </div>
          <Button
            variant="outline"
            onClick={() => {
              emitir.reset();
              dispatch({ type: "reset" });
            }}
          >
            Nueva compra
          </Button>
        </SuccessPanel>
      </div>
    );
  }

  const tot = totales(estado.renglones);

  return (
    <div className="flex flex-col gap-6 p-4 sm:h-full sm:min-h-0 sm:p-6">
      <div>
        <h1 className="text-lg font-semibold">Nueva compra</h1>
        <p className="text-sm text-muted-foreground">
          Elegí el proveedor, cargá el número de su comprobante y los artículos con su costo.
        </p>
      </div>

      <div className="grid gap-4 sm:min-h-0 sm:flex-1 lg:grid-cols-[1fr_20rem]">
        {/* Cada columna scrollea sola: la página nunca lo hace. */}
        <div className="flex flex-col gap-4 sm:min-h-0 sm:overflow-auto">
          <Card className="space-y-3 p-4">
            <div className="grid gap-3 sm:grid-cols-2">
              <Field className="gap-1.5">
                <FieldLabel className="text-xs">
                  Proveedor <span className="text-destructive">*</span>
                </FieldLabel>
                <SelectorProveedor
                  value={estado.proveedorCodigo}
                  onChange={(codigo) => dispatch({ type: "proveedor", codigo })}
                />
              </Field>
              <Field className="gap-1.5">
                <FieldLabel htmlFor="numero" className="text-xs">
                  N° de comprobante <span className="text-destructive">*</span>
                </FieldLabel>
                <Input
                  id="numero"
                  value={estado.numeroComprobante}
                  onChange={(e) => dispatch({ type: "numero", valor: e.target.value })}
                  placeholder="0001-00001234"
                  aria-label="Número de comprobante del proveedor"
                />
              </Field>
            </div>
            <BuscadorArticulo onAgregar={onAgregar} />
          </Card>

          {estado.renglones.length > 0 && (
            <Card className="divide-y overflow-hidden p-0">
              {estado.renglones.map((renglon, i) => (
                <RenglonCompraRow
                  key={`${renglon.articulo_codigo}-${i}`}
                  renglon={renglon}
                  onCampo={(campo, valor) => dispatch({ type: "renglon", i, campo, valor })}
                  onQuitar={() => dispatch({ type: "quitar", i })}
                />
              ))}
            </Card>
          )}

          <ResumenCompra
            estado={estado}
            tot={tot}
            onCondicion={(valor) => dispatch({ type: "condicion", valor })}
            onDeposito={(valor) => dispatch({ type: "deposito", valor })}
            onEmitir={() => emitir.mutate(estado, { onSuccess: () => dispatch({ type: "emitido" }) })}
            puede={puedeEmitir(estado)}
            cargando={emitir.isPending}
            error={emitir.error?.message}
          />
        </div>

        <div className="flex flex-col gap-2 sm:min-h-0">
          <h2 className="shrink-0 text-sm font-medium text-muted-foreground">Últimas compras</h2>
          <ListadoCompras
            className="sm:min-h-0 sm:flex-1 sm:overflow-auto"
            compras={compras.data?.items}
            isLoading={compras.isLoading}
            isError={compras.isError}
            onRetry={() => void compras.refetch()}
          />
        </div>
      </div>
    </div>
  );
}
