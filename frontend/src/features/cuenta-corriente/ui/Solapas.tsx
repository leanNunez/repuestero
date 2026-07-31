import { Solapas as SolapasBase, type SolapaDef } from "@/shared/ui/solapas";

import type { Solapa } from "../model/estado";

const SOLAPAS: readonly SolapaDef<Solapa>[] = [
  { id: "clientes", label: "Clientes" },
  { id: "proveedores", label: "Proveedores" },
];

interface Props {
  activa: Solapa;
  onCambiar: (tab: Solapa) => void;
}

/** El vocabulario de cuenta corriente sobre el tablist compartido. */
export function Solapas({ activa, onCambiar }: Props) {
  return (
    <SolapasBase
      solapas={SOLAPAS}
      activa={activa}
      onCambiar={onCambiar}
      etiqueta="Tipo de cuenta corriente"
    />
  );
}
