import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { App } from "./app/App.tsx";
// Tipografía de marca (docs/art-direction.md): Chivo para UI, Chivo Mono para importes.
// Self-hosted vía @fontsource: Vite bundlea los woff2, sin depender de Google Fonts.
import "@fontsource-variable/chivo";
import "@fontsource-variable/chivo-mono";
import "./index.css";
// Aplica el tema guardado (claro/oscuro) antes del primer render → sin flash.
import "./shared/theme/themeStore.ts";

// Tema claro por defecto; el usuario lo togglea desde la topbar (persistido en localStorage).
createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
