import { NumericFormat } from "react-number-format";

import { cn } from "@/shared/lib/cn";

interface Props {
  /** Valor CANÓNICO: número con punto decimal y sin separadores de miles, o "" si está vacío.
   *  Ej: "1000000.5". Es lo que espera el back y las validaciones (`montoValido`, etc.). */
  value: string;
  /** Emite el valor CANÓNICO en cada tecla. La máscara es-AR es puramente de presentación. */
  onChange: (canonico: string) => void;
  id?: string;
  "aria-label"?: string;
  "aria-describedby"?: string;
  placeholder?: string;
  disabled?: boolean;
  className?: string;
}

/** Campo para tipear plata con máscara argentina EN VIVO: punto de miles y coma decimal
 *  (`1.000.000,50`) mientras se escribe. Separa la representación que VE la persona de la
 *  CANÓNICA que viaja al back: adentro formatea, hacia afuera emite punto decimal sin separadores.
 *  Así las validaciones y cálculos (`Number(...)`) del resto del sistema no cambian. */
export function CampoMoneda({ value, onChange, className, ...rest }: Props) {
  return (
    <NumericFormat
      value={value}
      thousandSeparator="."
      decimalSeparator=","
      decimalScale={2}
      allowNegative={false}
      inputMode="decimal"
      onValueChange={(v) => onChange(v.value)}
      className={cn("tabular-nums", className)}
      {...rest}
    />
  );
}
