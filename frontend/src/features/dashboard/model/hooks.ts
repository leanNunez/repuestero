import { useQuery } from "@tanstack/react-query";

import { apiGet } from "@/shared/api/client";

import { margenesSchema, reposicionSchema, resumenSchema } from "../schema";

export function useResumen() {
  return useQuery({
    queryKey: ["dashboard", "resumen"],
    queryFn: () => apiGet("/dashboard/resumen", resumenSchema),
  });
}

export function useReposicion() {
  return useQuery({
    queryKey: ["dashboard", "reposicion"],
    queryFn: () => apiGet("/dashboard/reposicion", reposicionSchema),
  });
}

export function useMargenes() {
  return useQuery({
    queryKey: ["dashboard", "margenes"],
    queryFn: () => apiGet("/dashboard/margenes", margenesSchema),
  });
}
