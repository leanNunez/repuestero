import logging
from functools import lru_cache
from typing import Any
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)
_bearer = HTTPBearer(auto_error=False)


@lru_cache
def _jwks_client(jwks_url: str) -> jwt.PyJWKClient:
    return jwt.PyJWKClient(jwks_url, cache_keys=True)


def _decode(token: str, settings: Settings) -> dict[str, Any]:
    """Valida el JWT de Supabase.

    Proyectos nuevos firman con claves asimétricas (ES256/RS256) y publican el JWKS.
    Proyectos legacy firman con HS256 y un secreto simétrico. Soportamos los dos.
    """
    common = {
        "audience": settings.supabase_jwt_audience,
        "options": {"require": ["exp", "sub"]},
    }

    if settings.supabase_jwks_url:
        key = _jwks_client(settings.supabase_jwks_url).get_signing_key_from_jwt(token).key
        return jwt.decode(token, key, algorithms=["ES256", "RS256"], **common)

    if settings.supabase_jwt_secret:
        return jwt.decode(token, settings.supabase_jwt_secret, algorithms=["HS256"], **common)

    raise RuntimeError("Configurá SUPABASE_JWKS_URL o SUPABASE_JWT_SECRET")


class CurrentUser:
    def __init__(self, user_id: UUID, claims: dict[str, Any]) -> None:
        self.user_id = user_id
        self.claims = claims


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    settings: Settings = Depends(get_settings),
) -> CurrentUser:
    # Guard explícito ANTES de intentar decodificar: sin JWKS ni secret configurados esto es
    # un error de CONFIGURACIÓN del servidor, no un token inválido. Devolver 401 acá sería
    # peor que el 500 que reemplaza: le miente al cliente ("tu credencial está mal" con una
    # credencial perfecta), y el front borra el token al ver un 401 (bounceIf401 en
    # client.ts) — deja al usuario en un loop de login que nunca puede funcionar, sin
    # ningún mensaje, y entierra el bug de config en el ruido de los 401 legítimos.
    if not (settings.supabase_jwks_url or settings.supabase_jwt_secret):
        logger.error("Auth sin configurar: falta SUPABASE_JWKS_URL o SUPABASE_JWT_SECRET")
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Autenticación no configurada")

    if creds is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Falta el token")

    try:
        claims = _decode(creds.credentials, settings)
    except jwt.PyJWTError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token inválido") from exc

    return CurrentUser(user_id=UUID(claims["sub"]), claims=claims)
