import { getRouteApi } from "@tanstack/react-router";
import { useState } from "react";

import type { Cheque } from "@/entities/caja/schema";
import { pesos } from "@/entities/remito/formato";
import {
  ESTADOS_CHEQUE,
  FORMAS,
  cambiarSolapa,
  confirmacionTransicion,
  etiquetaEstado,
  etiquetaForma,
  filtrarEstado,
  filtrarForma,
  type Busqueda,
} from "@/features/caja/model/estado";
import {
  CARTERA_PAGE_SIZE,
  MOV_PAGE_SIZE,
  useCartera,
  useConciliarCheque,
  useMovimientosCaja,
  useRegistrarMovimiento,
  useSaldoCaja,
  useTransicionCheque,
  type Transicion,
} from "@/features/caja/model/hooks";
import { CarteraTable } from "@/features/caja/ui/CarteraTable";
import { FormularioConciliar } from "@/features/caja/ui/FormularioConciliar";
import { FormularioMovimiento } from "@/features/caja/ui/FormularioMovimiento";
import { MovimientosTable } from "@/features/caja/ui/MovimientosTable";
import { SaldoCards } from "@/features/caja/ui/SaldoCards";
import { Solapas } from "@/features/caja/ui/Solapas";
import { NativeSelect } from "@/shared/ui/native-select";
import { PageHeader } from "@/shared/ui/page-header";
import { PageLayout } from "@/shared/ui/page-layout";
import { Pagination } from "@/shared/ui/pagination";
import { toast } from "sonner";

const route = getRouteApi("/caja");

export function CajaPage() {
  const s = route.useSearch();
  const navigate = route.useNavigate();

  const saldo = useSaldoCaja();
  const movimientos = useMovimientosCaja(s.forma, s.page);
  const cartera = useCartera(s.estado, s.cpage);

  const registrar = useRegistrarMovimiento();
  const transicionar = useTransicionCheque();
  const conciliar = useConciliarCheque();

  // `null` = panel de conciliación cerrado. NO viaja en la URL: una conciliación a medio hacer no
  // es algo que quieras compartir en un link ni restaurar al volver atrás.
  const [aConciliar, setAConciliar] = useState<Cheque | null>(null);

  const ir = (proxima: Busqueda) => {
    if (proxima.tab !== s.tab) setAConciliar(null);
    navigate({ search: () => proxima, replace: true });
  };

  const enCaja = s.tab === "caja";

  return (
    <PageLayout>
      <PageHeader title="Caja" />
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Solapas activa={s.tab} onCambiar={(tab) => ir(cambiarSolapa(s, tab))} />

        {!enCaja && cartera.data && (
          <p className="text-sm text-muted-foreground">
            En cartera:{" "}
            <span className="font-medium tabular-nums text-foreground">
              {pesos(cartera.data.valor_en_cartera)}
            </span>
          </p>
        )}
      </div>

      <SaldoCards saldo={saldo.data} isLoading={saldo.isLoading} />

      {enCaja ? (
        <section
          id="panel-caja"
          role="tabpanel"
          aria-labelledby="solapa-caja"
          className="flex flex-col gap-3 sm:min-h-0 sm:flex-1"
        >
          <FormularioMovimiento
            cargando={registrar.isPending}
            error={registrar.error?.message ?? null}
            advertencias={registrar.data?.advertencias ?? []}
            onRegistrar={(v) => registrar.mutate(v)}
          />

          <div className="flex items-center gap-2">
            <label htmlFor="filtro-forma" className="text-xs text-muted-foreground">
              Forma
            </label>
            <NativeSelect
              id="filtro-forma"
              value={s.forma ?? ""}
              onChange={(e) => ir(filtrarForma(s, e.target.value || null))}
              containerClassName="w-auto"
            >
              <option value="">Todas</option>
              {FORMAS.map((f) => (
                <option key={f} value={f}>
                  {etiquetaForma(f)}
                </option>
              ))}
            </NativeSelect>
          </div>

          <MovimientosTable
            movimientos={movimientos.data?.items}
            isLoading={movimientos.isLoading}
            isError={movimientos.isError}
            onRetry={() => void movimientos.refetch()}
            containerClassName="sm:min-h-0 sm:flex-1"
          />

          <Pagination
            page={s.page}
            pageSize={MOV_PAGE_SIZE}
            total={movimientos.data?.total ?? 0}
            onPageChange={(page) => ir({ ...s, page })}
          />
        </section>
      ) : (
        <section
          id="panel-cartera"
          role="tabpanel"
          aria-labelledby="solapa-cartera"
          className="flex flex-col gap-3 sm:min-h-0 sm:flex-1"
        >
          <div className="flex items-center gap-2">
            <label htmlFor="filtro-estado" className="text-xs text-muted-foreground">
              Estado
            </label>
            <NativeSelect
              id="filtro-estado"
              value={s.estado ?? ""}
              onChange={(e) => ir(filtrarEstado(s, e.target.value || null))}
              containerClassName="w-auto"
            >
              <option value="">Todos</option>
              {ESTADOS_CHEQUE.map((e) => (
                <option key={e} value={e}>
                  {etiquetaEstado(e)}
                </option>
              ))}
            </NativeSelect>
          </div>

          <FormularioConciliar
            cheque={aConciliar}
            cargando={conciliar.isPending}
            error={conciliar.error?.message ?? null}
            onCerrar={() => {
              setAConciliar(null);
              conciliar.reset();
            }}
            onConciliar={(fecha) => {
              if (!aConciliar) return;
              conciliar.mutate(
                { id: aConciliar.id, fecha },
                {
                  onSuccess: () => {
                    setAConciliar(null);
                    toast.success("Cheque conciliado");
                  },
                },
              );
            }}
          />

          {transicionar.error && (
            <p role="alert" className="text-sm text-destructive">
              {transicionar.error.message}
            </p>
          )}

          <CarteraTable
            cheques={cartera.data?.items}
            isLoading={cartera.isLoading}
            isError={cartera.isError}
            onRetry={() => void cartera.refetch()}
            ocupado={transicionar.isPending ? (transicionar.variables?.id ?? null) : null}
            onTransicion={(cheque: Cheque, t: Transicion) => {
              transicionar.reset();
              transicionar.mutate(
                { id: cheque.id, transicion: t },
                { onSuccess: () => toast.success(confirmacionTransicion(t)) },
              );
            }}
            onConciliar={(cheque: Cheque) => {
              conciliar.reset();
              setAConciliar(cheque);
            }}
            containerClassName="sm:min-h-0 sm:flex-1"
          />

          <Pagination
            page={s.cpage}
            pageSize={CARTERA_PAGE_SIZE}
            total={cartera.data?.total ?? 0}
            onPageChange={(cpage) => ir({ ...s, cpage })}
          />
        </section>
      )}
    </PageLayout>
  );
}
