import { getRouteApi } from "@tanstack/react-router";
import { useEffect, useState } from "react";

import type { Movimiento } from "@/entities/cuenta-corriente/schema";
import { pesos } from "@/entities/remito/formato";
import {
  buscar,
  cambiarSolapa,
  seleccionar,
  signoSaldo,
  verTodos,
  type Busqueda,
  type ModoAjuste,
} from "@/features/cuenta-corriente/model/estado";
import {
  MOV_PAGE_SIZE,
  PAGE_SIZE,
  useAjustar,
  useAnularDocumento,
  useCuentas,
  useImputar,
  useMovimientos,
} from "@/features/cuenta-corriente/model/hooks";
import { ExtractoTable } from "@/features/cuenta-corriente/ui/ExtractoTable";
import { FormularioAjuste } from "@/features/cuenta-corriente/ui/FormularioAjuste";
import { FormularioAnulacion } from "@/features/cuenta-corriente/ui/FormularioAnulacion";
import { FormularioImputacion } from "@/features/cuenta-corriente/ui/FormularioImputacion";
import { ListadoCuentas } from "@/features/cuenta-corriente/ui/ListadoCuentas";
import { Solapas } from "@/features/cuenta-corriente/ui/Solapas";
import { Card } from "@/shared/ui/card";
import { PageHeader } from "@/shared/ui/page-header";
import { Pagination } from "@/shared/ui/pagination";
import { SearchInput } from "@/shared/ui/search-input";
import { EmptyState } from "@/shared/ui/states";

const route = getRouteApi("/cuenta-corriente");

export function CuentaCorrientePage() {
  const s = route.useSearch();
  const navigate = route.useNavigate();

  const cuentas = useCuentas(s.tab, s.page, s.q, s.todos);
  const movimientos = useMovimientos(s.tab, s.sel, s.mpage);
  const imputar = useImputar(s.tab);
  const ajustar = useAjustar(s.tab, s.sel);

  const anular = useAnularDocumento(s.tab);

  // `null` = formulario de ajuste cerrado. NO viaja en la URL: un ajuste a medio escribir no es
  // algo que quieras compartir en un link ni restaurar al volver atrás.
  const [modoAjuste, setModoAjuste] = useState<ModoAjuste | null>(null);
  // Mismo criterio para la anulación, con su propio estado: son dos operaciones distintas y tener
  // una sola variable haría que abrir una cierre la otra por accidente.
  const [aAnular, setAAnular] = useState<Movimiento | null>(null);

  // Toda la navegación pasa por acá: las transiciones son funciones puras de `estado.ts`, así que
  // la página no decide qué resetear — eso está testeado aparte.
  const ir = (proxima: Busqueda) => {
    // Cambiar de cuenta o de solapa cierra el ajuste. Si no, el formulario quedaría abierto en
    // modo reversa apuntando al movimiento de la cuenta ANTERIOR: el backend lo rechazaría por el
    // filtro de cliente, pero la pantalla estaría mintiendo hasta que la persona apriete.
    if (proxima.tab !== s.tab || proxima.sel !== s.sel) {
      setModoAjuste(null);
      setAAnular(null);
    }
    navigate({ search: () => proxima, replace: true });
  };

  const items = cuentas.data?.items ?? [];
  const total = cuentas.data?.total ?? 0;
  const cuenta = movimientos.data?.cuenta;

  // Página fuera de rango (URL manipulada, o una cobranza que sacó a la última cuenta del filtro).
  useEffect(() => {
    if (total > 0 && items.length === 0 && s.page > 1) ir({ ...s, page: 1 });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [total, items.length, s.page]);

  const esCliente = s.tab === "clientes";

  return (
    <div className="mx-auto max-w-6xl space-y-4 p-4 md:p-5">
      <PageHeader title="Cuenta corriente" />
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Solapas activa={s.tab} onCambiar={(tab) => ir(cambiarSolapa(s, tab))} />

        {cuentas.data && (
          <p className="text-sm text-muted-foreground">
            {esCliente ? "Neto a cobrar" : "Neto a pagar"}:{" "}
            <span className="font-medium tabular-nums text-foreground">
              {pesos(cuentas.data.saldo_total)}
            </span>
          </p>
        )}
      </div>

      <div className="grid gap-4 lg:grid-cols-[22rem_1fr]">
        {/* ---------------------------------------------------------------- listado de cuentas */}
        <section aria-label="Cuentas" className="space-y-3">
          <SearchInput
            value={s.q}
            onChange={(e) => ir(buscar(s, e.target.value))}
            placeholder={esCliente ? "Buscar cliente…" : "Buscar proveedor…"}
            aria-label={esCliente ? "Buscar cliente" : "Buscar proveedor"}
          />

          <label className="flex items-center gap-2 text-sm text-muted-foreground">
            <input
              type="checkbox"
              checked={s.todos}
              onChange={(e) => ir(verTodos(s, e.target.checked))}
              className="h-4 w-4 rounded border-input"
            />
            Ver también las cuentas en cero
          </label>

          <ListadoCuentas
            cuentas={items}
            seleccionada={s.sel}
            isLoading={cuentas.isLoading}
            isError={cuentas.isError}
            todos={s.todos}
            onSeleccionar={(id) => ir(seleccionar(s, id))}
            onRetry={() => void cuentas.refetch()}
          />

          <Pagination
            page={s.page}
            pageSize={PAGE_SIZE}
            total={total}
            onPageChange={(page) => ir({ ...s, page })}
          />
        </section>

        {/* ------------------------------------------------------------------------- extracto */}
        <section
          id={`panel-${s.tab}`}
          role="tabpanel"
          aria-labelledby={`solapa-${s.tab}`}
          className="space-y-3"
        >
          {s.sel === null ? (
            <Card className="p-0">
              <EmptyState
                title="Elegí una cuenta"
                hint="Vas a ver el detalle de movimientos y vas a poder registrar el pago."
              />
            </Card>
          ) : (
            <>
              {cuenta && (
                <Card className="flex flex-wrap items-baseline justify-between gap-2 p-3">
                  <div className="min-w-0">
                    <h2 className="truncate font-semibold">{cuenta.nombre}</h2>
                    <p className="text-xs text-muted-foreground tabular-nums">{cuenta.codigo}</p>
                  </div>
                  {/* aria-live: al registrar una cobranza el saldo cambia sin que se navegue a
                      ningún lado, así que hay que anunciarlo. */}
                  <p aria-live="polite" className="text-right">
                    <span className="block text-xs text-muted-foreground">Saldo</span>
                    <span className="text-lg font-semibold tabular-nums">
                      {pesos(cuenta.saldo)}
                    </span>
                    {signoSaldo(cuenta.saldo) === "a-favor" && (
                      <span className="block text-xs text-muted-foreground">a favor</span>
                    )}
                  </p>
                </Card>
              )}

              {cuenta && (
                <FormularioImputacion
                  tab={s.tab}
                  cuenta={cuenta}
                  cargando={imputar.isPending}
                  error={imputar.error?.message ?? null}
                  onImputar={(monto, fecha, formasPago) => {
                    imputar.mutate({ codigo: cuenta.codigo, monto, fecha, formasPago });
                  }}
                />
              )}

              <FormularioAjuste
                modo={modoAjuste}
                cargando={ajustar.isPending}
                error={ajustar.error?.message ?? null}
                onAbrir={() => setModoAjuste({ kind: "libre" })}
                onCerrar={() => {
                  setModoAjuste(null);
                  ajustar.reset();
                }}
                onAjustar={(payload) => {
                  ajustar.mutate(payload, { onSuccess: () => setModoAjuste(null) });
                }}
              />

              <FormularioAnulacion
                movimiento={aAnular}
                cargando={anular.isPending}
                error={anular.error?.message ?? null}
                onCerrar={() => {
                  setAAnular(null);
                  anular.reset();
                }}
                onAnular={(motivo) => {
                  if (aAnular?.ref_id == null) return;
                  anular.mutate(
                    { documentoId: aAnular.ref_id, motivo },
                    { onSuccess: () => setAAnular(null) },
                  );
                }}
              />

              <ExtractoTable
                movimientos={movimientos.data?.items}
                isLoading={movimientos.isLoading}
                isError={movimientos.isError}
                onRetry={() => void movimientos.refetch()}
                onRevertir={(m) => {
                  ajustar.reset();
                  setAAnular(null);
                  setModoAjuste({ kind: "storno", movimiento: m });
                }}
                onAnular={(m) => {
                  anular.reset();
                  setModoAjuste(null);
                  setAAnular(m);
                }}
              />

              <Pagination
                page={s.mpage}
                pageSize={MOV_PAGE_SIZE}
                total={movimientos.data?.total ?? 0}
                onPageChange={(mpage) => ir({ ...s, mpage })}
              />
            </>
          )}
        </section>
      </div>
    </div>
  );
}
