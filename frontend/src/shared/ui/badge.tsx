import { cva, type VariantProps } from "class-variance-authority";
import type { HTMLAttributes } from "react";

import { cn } from "@/shared/lib/cn";

const badgeVariants = cva(
  "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium",
  {
    variants: {
      variant: {
        default: "bg-muted text-muted-foreground",
        // Tinte del propio token (15% claro / 10% oscuro): AA verificado contra
        // los semánticos de index.css — se acabaron los amber/emerald crudos.
        warning: "bg-warning/15 text-warning dark:bg-warning/10",
        danger: "bg-destructive/10 text-destructive",
        success: "bg-success/15 text-success dark:bg-success/10",
      },
    },
    defaultVariants: { variant: "default" },
  },
);

type BadgeProps = HTMLAttributes<HTMLSpanElement> & VariantProps<typeof badgeVariants>;

export function Badge({ className, variant, ...props }: BadgeProps) {
  return <span className={cn(badgeVariants({ variant }), className)} {...props} />;
}
