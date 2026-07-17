"""Guard de SQL: valida y acota el SQL que genera el LLM ANTES de ejecutarlo.

Es la reja 5 (defensa en profundidad). La reja DURA es el rol read-only —que no puede escribir ni
aunque quiera—; esto atrapa el ataque antes, con mensajes claros, y garantiza un techo de filas.

Reglas: una sola sentencia, y que sea SELECT (o WITH…SELECT / UNION de SELECT). Cualquier DML/DDL
(INSERT/UPDATE/DELETE/DROP/…) o comando suelto (SET/COPY/GRANT) se rechaza. Se impone un LIMIT.
"""

import sqlglot
from sqlglot import exp

# Nodos que NO pueden aparecer en el árbol. `Command` cubre SET/COPY/GRANT/VACUUM y demás comandos
# que sqlglot no modela como expresiones estructuradas.
_PROHIBIDOS = (
    exp.Insert,
    exp.Update,
    exp.Delete,
    exp.Merge,
    exp.Create,
    exp.Drop,
    exp.Alter,
    exp.TruncateTable,
    exp.Command,
)


class SQLNoPermitido(ValueError):
    """El SQL generado no pasó el guard (no es un SELECT read-only de una sola sentencia)."""


def validar_y_acotar(sql: str, *, max_filas: int) -> str:
    """Devuelve el SQL saneado (con LIMIT) o levanta SQLNoPermitido."""
    try:
        arboles = [a for a in sqlglot.parse(sql, read="postgres") if a is not None]
    except Exception as exc:  # noqa: BLE001 — cualquier error de parseo es rechazo
        raise SQLNoPermitido("El SQL no se pudo parsear") from exc

    if len(arboles) != 1:
        raise SQLNoPermitido("Se permite exactamente una sentencia SQL")

    arbol = arboles[0]

    # La raíz tiene que ser una consulta de lectura.
    if not isinstance(arbol, (exp.Select, exp.Union)):
        raise SQLNoPermitido("Solo se permiten consultas SELECT")

    # Ni un solo nodo de escritura o DDL en todo el árbol (subconsultas incluidas).
    for clase in _PROHIBIDOS:
        if arbol.find(clase):
            raise SQLNoPermitido(f"Operación no permitida: {clase.__name__}")

    # Techo de filas duro (además del statement_timeout y del fetch acotado del executor).
    arbol = arbol.limit(max_filas)
    return arbol.sql(dialect="postgres")
