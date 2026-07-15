import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { App } from "./app/App.tsx";
import "./index.css";

// Tema claro por defecto (profesional para el ERP). El modo oscuro queda como toggle a futuro.
createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
