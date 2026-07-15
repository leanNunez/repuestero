import {
  createRootRoute,
  createRoute,
  createRouter,
  Outlet,
} from "@tanstack/react-router";

import { ArticuloPage } from "@/pages/catalogo/ArticuloPage";
import { CatalogoPage } from "@/pages/catalogo/CatalogoPage";
import { DashboardPage } from "@/pages/dashboard/DashboardPage";
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

const routeTree = rootRoute.addChildren([dashboardRoute, catalogoRoute, articuloRoute]);

export const router = createRouter({ routeTree });

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}
