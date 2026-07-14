from functools import lru_cache
from typing import Any
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import Settings, get_settings

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
    if creds is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Falta el token")

    try:
        claims = _decode(creds.credentials, settings)
    except jwt.PyJWTError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token inválido") from exc

    return CurrentUser(user_id=UUID(claims["sub"]), claims=claims)
