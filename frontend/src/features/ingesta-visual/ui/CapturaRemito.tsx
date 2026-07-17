import { Camera, Loader2, Upload } from "lucide-react";
import { useRef, useState } from "react";

import { Button } from "@/shared/ui/button";

const MAX_MB = 8;
const MIMES = ["image/jpeg", "image/png", "image/webp"];

interface Props {
  onImagen: (imagen_base64: string, mime: string) => void;
  cargando: boolean;
  error?: string | null;
}

/** Saca la foto (o la elige del disco) y la pasa como base64.
 *
 * `capture="environment"` hace que en un celular esto abra la cámara TRASERA directo, sin
 * una sola dependencia. Es exactamente el gesto del demo: el tipo está en el mostrador con
 * el remito en la mano.
 */
export function CapturaRemito({ onImagen, cargando, error }: Props) {
  const input = useRef<HTMLInputElement>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [errorLocal, setErrorLocal] = useState<string | null>(null);

  function elegir(file: File | undefined) {
    if (!file) return;
    setErrorLocal(null);

    // Los mismos techos que el server, chequeados acá: rebotar 10MB después de subirlos es
    // hacerle esperar a alguien para nada.
    if (!MIMES.includes(file.type)) {
      setErrorLocal("Tiene que ser una foto JPG, PNG o WEBP.");
      return;
    }
    if (file.size > MAX_MB * 1024 * 1024) {
      setErrorLocal(`La foto pesa ${(file.size / 1024 / 1024).toFixed(1)} MB. El máximo es ${MAX_MB} MB.`);
      return;
    }

    const reader = new FileReader();
    reader.onload = () => {
      const dataUrl = reader.result as string;
      setPreview(dataUrl);
      onImagen(dataUrl.split(",")[1], file.type);
    };
    reader.onerror = () => setErrorLocal("No pude leer el archivo. Probá de nuevo.");
    reader.readAsDataURL(file);
  }

  const mensaje = errorLocal ?? error;

  return (
    <div className="mx-auto flex max-w-lg flex-col items-center gap-4 py-10 text-center">
      <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-primary/10 text-primary">
        <Camera className="h-8 w-8" />
      </div>

      <div>
        <h2 className="text-lg font-semibold">Sacale una foto al remito</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Repu lee los renglones y te muestra qué va a cargar. Vos revisás antes de que se
          escriba nada.
        </p>
      </div>

      {preview && (
        <img
          src={preview}
          alt="Vista previa del remito"
          className="max-h-64 w-full rounded-lg border object-contain"
        />
      )}

      <input
        ref={input}
        type="file"
        accept="image/jpeg,image/png,image/webp"
        capture="environment"
        className="sr-only"
        onChange={(e) => elegir(e.target.files?.[0])}
        disabled={cargando}
      />

      <Button onClick={() => input.current?.click()} disabled={cargando}>
        {cargando ? (
          <>
            <Loader2 className="h-4 w-4 animate-spin" />
            Repu está leyendo la foto…
          </>
        ) : (
          <>
            <Upload className="h-4 w-4" />
            {preview ? "Elegir otra foto" : "Elegir foto"}
          </>
        )}
      </Button>

      {mensaje && (
        <p role="alert" className="text-sm font-medium text-destructive">
          {mensaje}
        </p>
      )}
    </div>
  );
}
