import { Car, Search } from "lucide-react";
import { useState, type FormEvent } from "react";

import { ArticuloTable } from "@/entities/articulo/ArticuloTable";
import {
  useCompatibilidad,
  type ConsultaCompat,
} from "@/features/compatibilidad/model/hooks";
import { Button } from "@/shared/ui/button";
import { Card } from "@/shared/ui/card";
import { Skeleton } from "@/shared/ui/skeleton";
import { EmptyState, ErrorState } from "@/shared/ui/states";

const inputClass =
  "h-9 w-full rounded-md border border-input bg-background px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background";

function Campo({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="flex flex-col gap-1 text-xs font-medium text-muted-foreground">
      {label}
      {children}
    </label>
  );
}

export function CompatibilidadPage() {
  const [marca, setMarca] = useState("");
  const [modelo, setModelo] = useState("");
  const [anio, setAnio] = useState("");
  const [consulta, setConsulta] = useState<ConsultaCompat | null>(null);

  const { data, isLoading, isError, refetch } = useCompatibilidad(
    consulta ?? { marca: "", modelo: "", anio: "" },
    consulta !== null,
  );

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (marca.trim() && modelo.trim()) {
      setConsulta({ marca: marca.trim(), modelo: modelo.trim(), anio: anio.trim() });
    }
  };

  const puedeBuscar = marca.trim().length > 0 && modelo.trim().length > 0;

  return (
    <div className="mx-auto max-w-6xl space-y-4 p-4 md:p-5">
      <div className="space-y-1">
        <h2 className="text-sm font-semibold">¿Qué repuestos le sirven a un vehículo?</h2>
        <p className="text-sm text-muted-foreground">
          Ej.: “el filtro de aceite para un Volkswagen Gol Trend 2015”. Marca y modelo son
          obligatorios.
        </p>
      </div>

      <Card className="p-4">
        <form
          onSubmit={submit}
          className="grid grid-cols-1 gap-3 sm:grid-cols-[1fr_1fr_7rem_auto] sm:items-end"
        >
          <Campo label="Marca *">
            <input
              value={marca}
              onChange={(e) => setMarca(e.target.value)}
              placeholder="Volkswagen"
              className={inputClass}
            />
          </Campo>
          <Campo label="Modelo *">
            <input
              value={modelo}
              onChange={(e) => setModelo(e.target.value)}
              placeholder="Gol Trend"
              className={inputClass}
            />
          </Campo>
          <Campo label="Año">
            <input
              value={anio}
              onChange={(e) => setAnio(e.target.value)}
              placeholder="2015"
              inputMode="numeric"
              className={inputClass}
            />
          </Campo>
          <Button type="submit" disabled={!puedeBuscar}>
            <Search className="h-4 w-4" />
            Buscar
          </Button>
        </form>
      </Card>

      {consulta === null ? (
        <div className="flex flex-col items-center justify-center gap-2 py-16 text-center">
          <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-muted">
            <Car className="h-6 w-6 text-muted-foreground" />
          </div>
          <p className="text-sm font-medium">Elegí un vehículo</p>
          <p className="max-w-sm text-sm text-muted-foreground">
            Cargá marca y modelo para ver los repuestos compatibles.
          </p>
        </div>
      ) : isLoading ? (
        <div className="space-y-2">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-11 w-full" />
          ))}
        </div>
      ) : isError ? (
        <ErrorState onRetry={() => void refetch()} />
      ) : !data || data.length === 0 ? (
        <EmptyState
          title="Sin compatibilidades"
          hint={`No encontramos repuestos cargados para ${consulta.marca} ${consulta.modelo}.`}
        />
      ) : (
        <>
          <p className="text-xs text-muted-foreground">
            {data.length} {data.length === 1 ? "repuesto compatible" : "repuestos compatibles"}
          </p>
          <ArticuloTable articulos={data} />
        </>
      )}
    </div>
  );
}
