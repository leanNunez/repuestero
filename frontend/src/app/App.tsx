import { QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider } from "@tanstack/react-router";

import { queryClient } from "@/shared/api/queryClient";
import { AuthGate } from "@/shared/auth/AuthGate";
import { BackendGate } from "@/shared/health/BackendGate";

import { router } from "./router";

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BackendGate>
        <AuthGate>
          <RouterProvider router={router} />
        </AuthGate>
      </BackendGate>
    </QueryClientProvider>
  );
}
