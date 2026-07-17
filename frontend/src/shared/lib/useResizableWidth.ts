import { useRef, useState, type KeyboardEvent, type PointerEvent } from "react";

const KEY = "repuestos-chat-width";
const MIN = 360;
const MAX = 900;
const STEP = 24;

function clamp(w: number): number {
  const max = Math.min(MAX, Math.round(window.innerWidth * 0.95));
  return Math.max(MIN, Math.min(max, w));
}

/**
 * Ancho de un panel anclado a la derecha, redimensionable arrastrando su borde izquierdo.
 * Persiste en localStorage. Soporta teclado (← ensancha, → angosta) para accesibilidad.
 */
export function useResizableWidth(defaultWidth = 448) {
  const [width, setWidth] = useState<number>(() => {
    const saved = Number(localStorage.getItem(KEY));
    return clamp(saved > 0 ? saved : defaultWidth);
  });
  const widthRef = useRef(width);

  const set = (w: number) => {
    const c = clamp(w);
    widthRef.current = c;
    setWidth(c);
  };

  const persist = () => localStorage.setItem(KEY, String(widthRef.current));

  const onPointerDown = (e: PointerEvent) => {
    e.preventDefault();
    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";

    // El panel está pegado a la derecha: ancho = distancia del cursor al borde derecho.
    const onMove = (ev: globalThis.PointerEvent) => set(window.innerWidth - ev.clientX);
    const onUp = () => {
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
      persist();
    };

    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);
  };

  const onKeyDown = (e: KeyboardEvent) => {
    if (e.key === "ArrowLeft") {
      e.preventDefault();
      set(widthRef.current + STEP);
      persist();
    } else if (e.key === "ArrowRight") {
      e.preventDefault();
      set(widthRef.current - STEP);
      persist();
    }
  };

  return { width, onPointerDown, onKeyDown };
}
