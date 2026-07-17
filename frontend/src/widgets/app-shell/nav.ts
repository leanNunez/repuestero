import {
  Banknote,
  Camera,
  Car,
  FileText,
  LayoutDashboard,
  Package,
  ShoppingCart,
  Truck,
  Users,
  Wallet,
  type LucideIcon,
} from "lucide-react";

export interface NavItem {
  to: string;
  label: string;
  icon: LucideIcon;
  exact?: boolean;
  /** 1 = funciona de verdad. 2 = placeholder "próximamente" (sin backend todavía). */
  fase: 1 | 2;
}

export interface NavGroup {
  label: string;
  items: NavItem[];
}

export const NAV_GROUPS: NavGroup[] = [
  {
    label: "Gestión",
    items: [
      { to: "/", label: "Inicio", icon: LayoutDashboard, exact: true, fase: 1 },
      { to: "/catalogo", label: "Catálogo", icon: Package, fase: 1 },
      { to: "/compatibilidad", label: "Compatibilidad", icon: Car, fase: 1 },
      { to: "/clientes", label: "Clientes", icon: Users, fase: 1 },
    ],
  },
  {
    label: "Operaciones",
    items: [
      { to: "/ingesta-visual", label: "Cargar remito", icon: Camera, fase: 1 },
      { to: "/ventas", label: "Ventas", icon: ShoppingCart, fase: 2 },
      { to: "/facturacion", label: "Facturación", icon: FileText, fase: 2 },
      { to: "/caja", label: "Caja", icon: Banknote, fase: 2 },
      { to: "/cuenta-corriente", label: "Cuenta corriente", icon: Wallet, fase: 2 },
      { to: "/compras", label: "Compras", icon: Truck, fase: 2 },
    ],
  },
];

/** Mapa ruta → etiqueta, para títulos de topbar y la pantalla "próximamente". */
export const NAV_LABELS: Record<string, string> = Object.fromEntries(
  NAV_GROUPS.flatMap((g) => g.items.map((i) => [i.to, i.label])),
);
