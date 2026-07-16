export type RepuState = "espera" | "pensando" | "error" | "respondiendo";

/** Cara de Repu según el estado. Cambia ojos/boca + un accesorio; el cuerpo es siempre el mismo. */
function Face({ state }: { state: RepuState }) {
  if (state === "pensando") {
    return (
      <>
        {/* ojos mirando hacia arriba */}
        <circle cx="40" cy="39" r="4" fill="#1e293b" />
        <circle cx="56" cy="39" r="4" fill="#1e293b" />
        <circle cx="41" cy="37.4" r="1.3" fill="#ffffff" />
        <circle cx="57" cy="37.4" r="1.3" fill="#ffffff" />
        {/* boca pensativa (línea) */}
        <path d="M43 49h8" stroke="#1e293b" strokeWidth="2.5" strokeLinecap="round" />
        {/* "..." pensando */}
        <g fill="#2f6fe0">
          <circle cx="70" cy="18" r="2" className="animate-pulse [animation-delay:-0.3s]" />
          <circle cx="76" cy="15" r="2" className="animate-pulse [animation-delay:-0.15s]" />
          <circle cx="82" cy="12" r="2" className="animate-pulse" />
        </g>
      </>
    );
  }

  if (state === "error") {
    return (
      <>
        {/* cejas preocupadas */}
        <path
          d="M35 34l8 3M61 34l-8 3"
          stroke="#1e293b"
          strokeWidth="2.2"
          strokeLinecap="round"
        />
        <circle cx="40" cy="41" r="3.6" fill="#1e293b" />
        <circle cx="56" cy="41" r="3.6" fill="#1e293b" />
        {/* boca ondulada */}
        <path
          d="M41 50q3.5 -3 7 0t7 0"
          stroke="#1e293b"
          strokeWidth="2.2"
          strokeLinecap="round"
          fill="none"
        />
        {/* gotita de sudor */}
        <path
          d="M66 39c0 2.2 -3 2.2 -3 0 0-1.6 1.5-3.6 1.5-3.6s1.5 2 1.5 3.6z"
          fill="#38bdf8"
          className="animate-pulse"
        />
      </>
    );
  }

  if (state === "respondiendo") {
    return (
      <>
        {/* ojos felices (arcos) */}
        <path
          d="M36 41q4 -4 8 0M52 41q4 -4 8 0"
          stroke="#1e293b"
          strokeWidth="2.6"
          strokeLinecap="round"
          fill="none"
        />
        {/* boca abierta sonriente */}
        <path d="M42 45q6 8 12 0z" fill="#1e293b" />
        {/* chispa */}
        <path
          d="M79 25l1.4 4 4 1.4 -4 1.4 -1.4 4 -1.4 -4 -4 -1.4 4 -1.4z"
          fill="#f59e0b"
          className="animate-pulse"
        />
      </>
    );
  }

  // espera
  return (
    <>
      <circle cx="40" cy="40" r="4.5" fill="#1e293b" />
      <circle cx="56" cy="40" r="4.5" fill="#1e293b" />
      <circle cx="41.6" cy="38.4" r="1.5" fill="#ffffff" />
      <circle cx="57.6" cy="38.4" r="1.5" fill="#ffffff" />
      <path
        d="M41 48q7 6 14 0"
        stroke="#1e293b"
        strokeWidth="2.5"
        strokeLinecap="round"
        fill="none"
      />
    </>
  );
}

/** Repu — mascota del asistente (robot mecánico). 4 estados con gesto. SVG plano, sin assets. */
export function RepuMascot({
  className,
  state = "espera",
}: {
  className?: string;
  state?: RepuState;
}) {
  return (
    <svg
      viewBox="0 0 96 120"
      className={className}
      role="img"
      aria-label={`Repu (${state})`}
      xmlns="http://www.w3.org/2000/svg"
    >
      <ellipse cx="48" cy="114" rx="28" ry="4" fill="#1e293b" opacity="0.12" />

      {/* brazo derecho + llave inglesa */}
      <g transform="rotate(16 74 52)">
        <rect x="70" y="60" width="9" height="24" rx="4.5" fill="#2f6fe0" />
        <rect x="71.5" y="30" width="6" height="30" rx="3" fill="#f59e0b" />
        <path
          d="M74.5 22a7 7 0 1 0 0 14 7 7 0 0 0 5-2l-4-3 4-3a7 7 0 0 0-5-6z"
          fill="#f59e0b"
        />
      </g>

      {/* cuerpo / overol */}
      <rect x="24" y="60" width="48" height="44" rx="13" fill="#2f6fe0" />
      <rect x="17" y="62" width="9" height="24" rx="4.5" fill="#2f6fe0" />
      <rect x="34" y="66" width="28" height="26" rx="6" fill="#dbe6ff" />
      <path d="M37 66l-4-6M59 66l4-6" stroke="#dbe6ff" strokeWidth="4" strokeLinecap="round" />
      <circle cx="42" cy="74" r="2" fill="#2f6fe0" />
      <circle cx="54" cy="74" r="2" fill="#2f6fe0" />

      {/* cuello */}
      <rect x="43" y="54" width="10" height="8" fill="#1e4fb0" />

      {/* cabeza */}
      <rect
        x="26"
        y="22"
        width="44"
        height="36"
        rx="13"
        fill="#ffffff"
        stroke="#2f6fe0"
        strokeWidth="3"
      />
      <circle cx="32" cy="47" r="3" fill="#f59e0b" opacity="0.35" />
      <circle cx="64" cy="47" r="3" fill="#f59e0b" opacity="0.35" />

      <Face state={state} />

      {/* antena (roja si hay error) */}
      <line x1="48" y1="10" x2="48" y2="20" stroke="#2f6fe0" strokeWidth="3" />
      <circle cx="48" cy="8" r="3.5" fill={state === "error" ? "#ef4444" : "#f59e0b"} />
    </svg>
  );
}
