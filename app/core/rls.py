from collections.abc import Iterator
from uuid import UUID

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import ORG_GUC, USER_GUC, SessionLocal, set_guc
from app.core.models import Miembro
from app.core.security import CurrentUser, get_current_user


class TenantContext:
    def __init__(self, session: Session, org_id: UUID, user_id: UUID) -> None:
        self.session = session
        self.org_id = org_id
        self.user_id = user_id


def get_tenant(user: CurrentUser = Depends(get_current_user)) -> Iterator[TenantContext]:
    """Abre la sesión del request con el tenant ya encerrado por RLS.

    El orden importa y es el único que funciona:

    1. Se fija `app.current_user_id`. La política de `miembros` filtra por ESE valor,
       así que el usuario solo puede ver sus propias membresías.
    2. Se resuelve el `org_id` leyendo `miembros`. Si no hay fila, no hay org: 403.
       El `org_id` NUNCA viene del JWT ni del cliente — sale de la base. Un token
       manipulado no puede pedir una org que no le corresponde.
    3. Se fija `app.current_org_id`. De acá en adelante, TODA query de la transacción
       está encerrada en ese tenant por las políticas de RLS.

    Ningún service abre su propia sesión. Todos reciben esta.
    """
    session = SessionLocal()
    try:
        set_guc(session, USER_GUC, str(user.user_id))

        org_id = session.scalar(select(Miembro.org_id).where(Miembro.user_id == user.user_id))
        if org_id is None:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN, "El usuario no pertenece a ninguna organización"
            )

        set_guc(session, ORG_GUC, str(org_id))

        yield TenantContext(session=session, org_id=org_id, user_id=user.user_id)
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
