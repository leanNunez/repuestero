import { CheckCircle2 } from "lucide-react";
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

const inputClass =
  "h-9 w-full rounded-md border border-input bg-background px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring";

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
      <div className="mx-auto flex max-w-lg flex-col items-center gap-4 p-4 py-10 text-center sm:p-6">
        <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-400">
          <CheckCircle2 className="h-8 w-8" />
        </div>
        <div>
          <h2 className="text-lg font-semibold">Compra registrada</h2>
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
      </div>
    );
  }

  const tot = totales(estado.renglones);

  return (
    <div className="space-y-6 p-4 sm:p-6">
      <div>
        <h1 className="text-lg font-semibold">Nueva compra</h1>
        <p className="text-sm text-muted-foreground">
          Elegí el proveedor, cargá el número de su comprobante y los artículos con su costo.
        </p>
      </div>

      <div className="grid gap-4 lg:grid-cols-[1fr_20rem]">
        <div className="space-y-4">
          <Card className="space-y-3 p-4">
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="space-y-1">
                <label className="text-xs font-medium">
                  Proveedor <span className="text-destructive">*</span>
                </label>
                <SelectorProveedor
                  value={estado.proveedorCodigo}
                  onChange={(codigo) => dispatch({ type: "proveedor", codigo })}
                />
              </div>
              <div className="space-y-1">
                <label htmlFor="numero" className="text-xs font-medium">
                  N° de comprobante <span className="text-destructive">*</span>
                </label>
                <input
                  id="numero"
                  value={estado.numeroComprobante}
                  onChange={(e) => dispatch({ type: "numero", valor: e.target.value })}
                  placeholder="0001-00001234"
                  className={inputClass}
                  aria-label="Número de comprobante del proveedor"
                />
              </div>
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

        <div className="space-y-2">
          <h2 className="text-sm font-medium text-muted-foreground">Últimas compras</h2>
          <ListadoCompras
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
