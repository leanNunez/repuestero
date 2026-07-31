import { Solapas as SolapasBase, type SolapaDef } from "@/shared/ui/solapas";

import type { Solapa } from "../model/estado";

const SOLAPAS: readonly SolapaDef<Solapa>[] = [
  { id: "caja", label: "Caja" },
  { id: "cartera", label: "Cartera" },
];

interface Props {
  activa: Solapa;
  onCambiar: (tab: Solapa) => void;
}

/** El vocabulario de caja sobre el tablist compartido. */
export function Solapas({ activa, onCambiar }: Props) {
  return (
    <SolapasBase
      solapas={SOLAPAS}
      activa={activa}
      onCambiar={onCambiar}
      etiqueta="Caja y cartera de cheques"
    />
  );
}
