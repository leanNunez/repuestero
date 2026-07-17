import { AlertTriangle, Info } from "lucide-react";
import { useReducer } from "react";

import { pesos } from "@/entities/remito/formato";

import { ESTADO_INICIAL, puedeConfirmar, reducer } from "@/features/ingesta-visual/model/estado";
import {
  useConfirmarRemito,
  useExtraerRemito,
} from "@/features/ingesta-visual/model/hooks";
import { CapturaRemito } from "@/features/ingesta-visual/ui/CapturaRemito";
import { RenglonEditableRow } from "@/features/ingesta-visual/ui/RenglonEditable";
import {
  ResultadoCarga,
  ResumenConfirmar,
} from "@/features/ingesta-visual/ui/ResumenConfirmar";
import { Card } from "@/shared/ui/card";

export function IngestaVisualPage() {
  const [estado, dispatch] = useReducer(reducer, ESTADO_INICIAL);
  const extraer = useExtraerRemito();
  const confirmar = useConfirmarRemito();

  function onImagen(imagen_base64: string, mime: string) {
    extraer.mutate(
      { imagen_base64, mime },
      { onSuccess: (propuesta) => dispatch({ type: "propuesta", propuesta }) },
    );
  }

  if (estado.paso === "listo" && confirmar.data) {
    return (
      <div className="p-4 sm:p-6">
        <ResultadoCarga
          resultado={confirmar.data}
          onOtro={() => {
            confirmar.reset();
            extraer.reset();
            dispatch({ type: "reset" });
          }}
        />
      </div>
    );
  }

  if (estado.paso === "capturar" || !estado.propuesta) {
    return (
      <div className="p-4 sm:p-6">
        <CapturaRemito
          onImagen={onImagen}
          cargando={extraer.isPending}
          error={extraer.error?.message}
        />
      </div>
    );
  }

  const p = estado.propuesta;

  // El remito ya está cargado: no hay nada para revisar y no se llamó al modelo.
  if (p.ya_procesado) {
    return (
      <div className="mx-auto max-w-lg p-4 text-center sm:p-6">
        <Card className="space-y-3 p-6">
          <Info className="mx-auto h-8 w-8 text-muted-foreground" />
          <h2 className="text-lg font-semibold">Este remito ya se cargó</h2>
          <p className="text-sm text-muted-foreground">
            {p.numero_remito && `Es el remito ${p.numero_remito}. `}
            Se cargó el {p.procesado_en ? new Date(p.procesado_en).toLocaleString("es-AR") : "—"}.
          </p>
          <button
            className="text-sm font-medium text-primary underline-offset-4 hover:underline"
            onClick={() => {
              extraer.reset();
              dispatch({ type: "reset" });
            }}
          >
            Cargar otro
          </button>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-4 p-4 sm:p-6">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <div>
          <h1 className="text-lg font-semibold">Revisá lo que leyó Repu</h1>
          <p className="text-sm text-muted-foreground">
            Nada se escribe hasta que confirmes. Destildá lo que no quieras cargar.
          </p>
        </div>
        {p.total_declarado && (
          <p className="text-sm text-muted-foreground">
            Total del remito: <span className="font-medium">{pesos(p.total_declarado)}</span> ·
            leído: <span className="font-medium">{pesos(p.total_calculado)}</span>
          </p>
        )}
      </div>

      {p.advertencias.length > 0 && (
        <ul className="space-y-1.5 rounded-lg bg-amber-50 p-3 text-sm text-amber-900 dark:bg-amber-950/40 dark:text-amber-200">
          {p.advertencias.map((a) => (
            <li key={a} className="flex gap-2">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
              {a}
            </li>
          ))}
        </ul>
      )}

      <Card className="overflow-hidden p-0">
        {estado.renglones.map((r, i) => (
          <RenglonEditableRow
            key={`${r.codigo ?? "s"}-${i}`}
            renglon={r}
            onCampo={(campo, valor) => dispatch({ type: "renglon", i, campo, valor })}
          />
        ))}
      </Card>

      <ResumenConfirmar
        estado={estado}
        onCampo={(campo, valor) => dispatch({ type: "campo", campo, valor })}
        onConfirmar={() =>
          confirmar.mutate(estado, { onSuccess: () => dispatch({ type: "confirmado" }) })
        }
        puede={puedeConfirmar(estado)}
        cargando={confirmar.isPending}
        error={confirmar.error?.message}
      />
    </div>
  );
}
