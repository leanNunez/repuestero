import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { App } from "./app/App.tsx";
import "./index.css";
// Aplica el tema guardado (claro/oscuro) antes del primer render → sin flash.
import "./shared/theme/themeStore.ts";

// Tema claro por defecto; el usuario lo togglea desde la topbar (persistido en localStorage).
createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
