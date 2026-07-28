import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { Combobox, type OpcionCombobox } from "./combobox";

const opciones: OpcionCombobox[] = [
  { clave: "C1", etiqueta: "Aceites Uno", detalle: "30-71233445-9" },
  { clave: "C2", etiqueta: "Aceites Dos", detalle: null },
];

const props = {
  label: "Cliente",
  placeholder: "Buscá…",
  q: "",
  onBuscar: vi.fn(),
  opciones: [],
  elegido: null,
  onElegir: vi.fn(),
  onLimpiar: vi.fn(),
  buscando: false,
  fallo: false,
};

describe("Combobox", () => {
  it("sin texto no despliega ninguna lista", () => {
    render(<Combobox {...props} />);

    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
    expect(screen.getByRole("combobox")).toHaveAttribute("aria-expanded", "false");
  });

  it("elegir con el mouse devuelve la opción entera", () => {
    const onElegir = vi.fn();
    render(<Combobox {...props} q="aceites" opciones={opciones} onElegir={onElegir} />);

    fireEvent.mouseDown(screen.getByRole("option", { name: /Aceites Dos/ }));

    expect(onElegir).toHaveBeenCalledWith(opciones[1]);
  });

  it("se puede elegir sin tocar el mouse", () => {
    // En el mostrador se busca con una mano y se teclea con la otra.
    const onElegir = vi.fn();
    render(<Combobox {...props} q="aceites" opciones={opciones} onElegir={onElegir} />);

    const input = screen.getByRole("combobox");
    fireEvent.keyDown(input, { key: "ArrowDown" });
    fireEvent.keyDown(input, { key: "ArrowDown" });
    fireEvent.keyDown(input, { key: "Enter" });

    expect(onElegir).toHaveBeenCalledWith(opciones[1]);
  });

  it("la flecha apunta a la opción activa por aria-activedescendant", () => {
    // El foco NUNCA se va del input: es lo que permite seguir escribiendo mientras se navega.
    render(<Combobox {...props} q="aceites" opciones={opciones} />);

    const input = screen.getByRole("combobox");
    fireEvent.keyDown(input, { key: "ArrowDown" });

    expect(input).toHaveAttribute("aria-activedescendant", "lista-cliente-opcion-0");
    expect(screen.getByRole("option", { name: /Aceites Uno/ })).toHaveAttribute(
      "aria-selected",
      "true",
    );
  });

  it("Enter sin nada resaltado no elige a nadie", () => {
    // Escribir y apretar Enter para confirmar el texto no puede facturarle al primero de la lista.
    const onElegir = vi.fn();
    render(<Combobox {...props} q="aceites" opciones={opciones} onElegir={onElegir} />);

    fireEvent.keyDown(screen.getByRole("combobox"), { key: "Enter" });

    expect(onElegir).not.toHaveBeenCalled();
  });

  it("Escape limpia la búsqueda", () => {
    const onBuscar = vi.fn();
    render(<Combobox {...props} q="aceites" opciones={opciones} onBuscar={onBuscar} />);

    fireEvent.keyDown(screen.getByRole("combobox"), { key: "Escape" });

    expect(onBuscar).toHaveBeenCalledWith("");
  });

  it("con uno elegido muestra qué se eligió, no el buscador", () => {
    render(<Combobox {...props} elegido={opciones[0]} />);

    expect(screen.getByText("Aceites Uno")).toBeInTheDocument();
    expect(screen.queryByRole("combobox")).not.toBeInTheDocument();
  });

  it("el botón de limpiar dice de qué se está cambiando", () => {
    const onLimpiar = vi.fn();
    render(<Combobox {...props} elegido={opciones[0]} onLimpiar={onLimpiar} />);

    fireEvent.click(screen.getByRole("button", { name: "Cambiar de cliente" }));

    expect(onLimpiar).toHaveBeenCalled();
  });

  it("avisa cuando la búsqueda falla, en vez de decir que no hay resultados", () => {
    // Un "sin resultados" ante un error de red hace que el operador dé de alta algo que ya existe.
    render(<Combobox {...props} q="aceites" fallo />);

    expect(screen.getByRole("alert")).toHaveTextContent(/No pude buscar/);
  });

  it("mientras busca no dice que no hay nada", () => {
    render(<Combobox {...props} q="aceites" buscando />);

    expect(screen.getByText("Buscando…")).toBeInTheDocument();
    expect(screen.queryByText(/Sin resultados/)).not.toBeInTheDocument();
  });

  it("una opción sin detalle no rompe la fila", () => {
    render(<Combobox {...props} q="aceites" opciones={opciones} />);

    expect(screen.getByRole("option", { name: /Aceites Dos/ })).toBeInTheDocument();
  });
});
