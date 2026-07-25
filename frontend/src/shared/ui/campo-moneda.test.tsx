import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";

import { CampoMoneda } from "./campo-moneda";

/** El componente es controlado: sin un padre que le devuelva el valor, tipear no actualiza el
 *  display. Este wrapper cierra el ciclo y expone el canónico emitido para poder afirmarlo. */
function Wrapper({ onCanonico }: { onCanonico?: (v: string) => void }) {
  const [value, setValue] = useState("");
  return (
    <CampoMoneda
      value={value}
      onChange={(v) => {
        setValue(v);
        onCanonico?.(v);
      }}
      aria-label="Monto"
    />
  );
}

describe("CampoMoneda", () => {
  it("formatea los miles con punto mientras se tipea y emite el canónico", async () => {
    const user = userEvent.setup();
    const spy = vi.fn();
    render(<Wrapper onCanonico={spy} />);

    const input = screen.getByLabelText("Monto");
    await user.type(input, "1000000");

    expect(input).toHaveValue("1.000.000");
    expect(spy).toHaveBeenLastCalledWith("1000000");
  });

  it("usa la coma para los centavos y emite punto decimal", async () => {
    const user = userEvent.setup();
    const spy = vi.fn();
    render(<Wrapper onCanonico={spy} />);

    const input = screen.getByLabelText("Monto");
    await user.type(input, "1000000,5");

    expect(input).toHaveValue("1.000.000,5");
    expect(spy).toHaveBeenLastCalledWith("1000000.5");
  });

  it("ignora el signo negativo", async () => {
    const user = userEvent.setup();
    render(<Wrapper />);

    const input = screen.getByLabelText("Monto");
    await user.type(input, "-5");

    expect(input).toHaveValue("5");
  });

  it("ignora las letras", async () => {
    const user = userEvent.setup();
    render(<Wrapper />);

    const input = screen.getByLabelText("Monto");
    await user.type(input, "abc12");

    expect(input).toHaveValue("12");
  });
});
