import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { MessageBubble } from "./MessageBubble";
import type { Message } from "./types";

describe("MessageBubble", () => {
  it("renderiza el contenido y la tabla del resultado SQL", () => {
    const m: Message = {
      id: "1",
      role: "assistant",
      content: "Hay 20 artículos.",
      streaming: false,
      result: { sql: "SELECT COUNT(*)", filas: [{ count: 20 }] },
    };
    render(<MessageBubble message={m} />);

    expect(screen.getByText("Hay 20 artículos.")).toBeInTheDocument();
    expect(screen.getByText("count")).toBeInTheDocument();
    expect(screen.getByText("20")).toBeInTheDocument();
  });

  it("renderiza el mensaje de bloqueo", () => {
    const m: Message = {
      id: "1",
      role: "assistant",
      content: "No puedo procesar esa consulta.",
      streaming: false,
      blocked: true,
    };
    render(<MessageBubble message={m} />);
    expect(screen.getByText("No puedo procesar esa consulta.")).toBeInTheDocument();
  });
});
