import { useReducer, useState } from "react";

import type { ArticuloItem } from "@/entities/articulo/schema";
import { pesos } from "@/entities/remito/formato";
import type { VentaLeer } from "@/entities/venta/schema";
import { NotaCreditoDialog } from "@/features/notas-credito/ui/NotaCreditoDialog";
import { ESTADO_INICIAL, puedeEmitir, reducer, totales } from "@/features/ventas/model/estado";
import { fetchPrecioSugerido, useEmitirVenta, useVentas } from "@/features/ventas/model/hooks";
import { BuscadorArticulo } from "@/features/ventas/ui/BuscadorArticulo";
import { ListadoVentas } from "@/features/ventas/ui/ListadoVentas";
import { RenglonVentaRow } from "@/features/ventas/ui/RenglonVentaRow";
import { ResumenVenta } from "@/features/ventas/ui/ResumenVenta";
import { SelectorCliente } from "@/features/ventas/ui/SelectorCliente";
import { Button } from "@/shared/ui/button";
import { Card } from "@/shared/ui/card";
import { Field, FieldLabel } from "@/shared/ui/field";
import { SuccessPanel } from "@/shared/ui/success-panel";
import { WarningList } from "@/shared/ui/warning-list";

function comprobanteLabel(tipo: string, ptoVenta: number, numero: number): string {
  return `${tipo} ${String(ptoVenta).padStart(4, "0")}-${String(numero).padStart(8, "0")}`;
}

export function VentasPage() {
  const [estado, dispatch] = useReducer(reducer, ESTADO_INICIAL);
  const [ncVenta, setNcVenta] = useState<VentaLeer | null>(null);
  const emitir = useEmitirVenta();
  const ventas = useVentas();

  async function onAgregar(a: ArticuloItem) {
    // Precarga el precio de la lista del cliente (o Mostrador). Si no hay, se tipea a mano.
    let precio = "";
    let lista: string | null = null;
    try {
      const sug = await fetchPrecioSugerido(a.codigo, estado.clienteCodigo || undefined);
      precio = sug.precio ?? "";
      lista = sug.lista_codigo;
    } catch {
      /* sin precio precargado: el operador lo completa */
    }
    dispatch({
      type: "agregar",
      renglon: {
        articulo_codigo: a.codigo,
        detalle: a.detalle,
        cantidad: "1",
        precio_unitario: precio,
        alicuota_iva: a.alicuota_iva,
        lista_codigo: lista,
      },
    });
  }

  if (estado.paso === "listo" && emitir.data) {
    const r = emitir.data;
    return (
      <div className="mx-auto max-w-lg p-4 py-10 sm:p-6">
        <SuccessPanel>
          <div>
            <h1 className="text-lg font-semibold">Venta emitida</h1>
            <p className="mt-1 text-sm text-muted-foreground">
              Comprobante {comprobanteLabel(r.tipo, r.pto_venta, r.numero)} · Total {pesos(r.total)}
            </p>
          </div>
          {/* La venta YA se emitió: esto no es un error, es algo para mirar. Va en el panel de
              éxito y no en un toast porque el toast se va y el cliente sigue excedido. */}
          <WarningList avisos={r.advertencias} />
          <Button
            variant="outline"
            onClick={() => {
              emitir.reset();
              dispatch({ type: "reset" });
            }}
          >
            Nueva venta
          </Button>
        </SuccessPanel>
      </div>
    );
  }

  const tot = totales(estado.renglones);

  return (
    <div className="flex flex-col gap-6 p-4 sm:h-full sm:min-h-0 sm:p-6">
      <div>
        <h1 className="text-lg font-semibold">Nueva venta</h1>
        <p className="text-sm text-muted-foreground">
          Elegí el cliente, agregá los artículos y emití el comprobante.
        </p>
      </div>

      <div className="grid gap-4 sm:min-h-0 sm:flex-1 lg:grid-cols-[1fr_20rem]">
        {/* Cada columna scrollea sola: la página nunca lo hace. */}
        <div className="flex flex-col gap-4 sm:min-h-0 sm:overflow-auto">
          <Card className="space-y-3 p-4">
            <Field className="gap-1.5">
              <FieldLabel className="text-xs">
                Cliente <span className="text-destructive">*</span>
              </FieldLabel>
              <SelectorCliente
                value={estado.clienteCodigo}
                onChange={(codigo) => dispatch({ type: "cliente", codigo })}
              />
            </Field>
            <BuscadorArticulo onAgregar={onAgregar} />
          </Card>

          {estado.renglones.length > 0 && (
            <Card className="divide-y overflow-hidden p-0">
              {estado.renglones.map((renglon, i) => (
                <RenglonVentaRow
                  key={`${renglon.articulo_codigo}-${i}`}
                  renglon={renglon}
                  onCampo={(campo, valor) => dispatch({ type: "renglon", i, campo, valor })}
                  onQuitar={() => dispatch({ type: "quitar", i })}
                />
              ))}
            </Card>
          )}

          <ResumenVenta
            estado={estado}
            tot={tot}
            onCondicion={(valor) => dispatch({ type: "condicion", valor })}
            onDeposito={(valor) => dispatch({ type: "deposito", valor })}
            onEmitir={() =>
              emitir.mutate(estado, { onSuccess: () => dispatch({ type: "emitido" }) })
            }
            puede={puedeEmitir(estado)}
            cargando={emitir.isPending}
            error={emitir.error?.message}
          />
        </div>

        <div className="flex flex-col gap-2 sm:min-h-0">
          <h2 className="shrink-0 text-sm font-medium text-muted-foreground">Últimas ventas</h2>
          <ListadoVentas
            className="sm:min-h-0 sm:flex-1 sm:overflow-auto"
            ventas={ventas.data?.items}
            isLoading={ventas.isLoading}
            isError={ventas.isError}
            onRetry={() => void ventas.refetch()}
            onNotaCredito={setNcVenta}
          />
        </div>
      </div>

      <NotaCreditoDialog venta={ncVenta} onClose={() => setNcVenta(null)} />
    </div>
  );
}
