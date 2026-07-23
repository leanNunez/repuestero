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
import { ComprasPage } from "@/pages/compras/ComprasPage";
import { DashboardPage } from "@/pages/dashboard/DashboardPage";
import { IngestaVisualPage } from "@/pages/ingesta-visual/IngestaVisualPage";
import { ProximamentePage } from "@/pages/proximamente/ProximamentePage";
import { VentasPage } from "@/pages/ventas/VentasPage";
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
  validateSearch: (
    search: Record<string, unknown>,
  ): { q: string; page: number; rubro: string; marca: string } => {
    const page = Number(search.page);
    return {
      q: typeof search.q === "string" ? search.q : "",
      page: Number.isInteger(page) && page >= 1 ? page : 1,
      rubro: typeof search.rubro === "string" ? search.rubro : "",
      marca: typeof search.marca === "string" ? search.marca : "",
    };
  },
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

const ventasRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/ventas",
  component: VentasPage,
});

const comprasRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/compras",
  component: ComprasPage,
});

// Módulos de Fase 2 todavía sin backend: navegables, pero caen en la pantalla "próximamente".
// `/ventas` y `/compras` salieron de acá: ya tienen su mostrador de verdad contra el backend.
const FASE2_PATHS = ["/facturacion", "/caja", "/cuenta-corriente"] as const;

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
  ventasRoute,
  comprasRoute,
  ...fase2Routes,
]);

export const router = createRouter({ routeTree });

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}
