import {
  createRootRoute,
  createRoute,
  createRouter,
  Outlet,
} from "@tanstack/react-router";

import { ArticuloPage } from "@/pages/catalogo/ArticuloPage";
import { CatalogoPage } from "@/pages/catalogo/CatalogoPage";
import { ClientesPage } from "@/pages/clientes/ClientesPage";
import { CompatibilidadPage } from "@/pages/compatibilidad/CompatibilidadPage";
import { DashboardPage } from "@/pages/dashboard/DashboardPage";
import { IngestaVisualPage } from "@/pages/ingesta-visual/IngestaVisualPage";
import { ProximamentePage } from "@/pages/proximamente/ProximamentePage";
import { AppShell } from "@/widgets/app-shell/AppShell";

const rootRoute = createRootRoute({
  component: () => (
    <AppShell>
      <Outlet />
    </AppShell>
  ),
});

const dashboardRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/",
  component: DashboardPage,
});

const catalogoRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/catalogo",
  component: CatalogoPage,
  validateSearch: (search: Record<string, unknown>): { q: string } => ({
    q: typeof search.q === "string" ? search.q : "",
  }),
});

const articuloRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/catalogo/$codigo",
  component: ArticuloPage,
});

const compatibilidadRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/compatibilidad",
  component: CompatibilidadPage,
});

const clientesRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/clientes",
  component: ClientesPage,
});

const ingestaVisualRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/ingesta-visual",
  component: IngestaVisualPage,
});

// Módulos de Fase 2: navegables, pero todos caen en la pantalla "próximamente".
// `/productos/nuevo` salió de acá: cargar un remito por foto ES el alta de productos y
// ya funciona de verdad contra el backend.
const FASE2_PATHS = [
  "/ventas",
  "/facturacion",
  "/caja",
  "/cuenta-corriente",
  "/compras",
] as const;

const fase2Routes = FASE2_PATHS.map((path) =>
  createRoute({ getParentRoute: () => rootRoute, path, component: ProximamentePage }),
);

const routeTree = rootRoute.addChildren([
  dashboardRoute,
  catalogoRoute,
  articuloRoute,
  compatibilidadRoute,
  clientesRoute,
  ingestaVisualRoute,
  ...fase2Routes,
]);

export const router = createRouter({ routeTree });

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}
