import { QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider } from "@tanstack/react-router";

import { queryClient } from "@/shared/api/queryClient";
import { DevTokenGate } from "@/shared/auth/DevTokenGate";

import { router } from "./router";

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <DevTokenGate>
        <RouterProvider router={router} />
      </DevTokenGate>
    </QueryClientProvider>
  );
}
