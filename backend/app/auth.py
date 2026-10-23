from dataclasses import dataclass
from functools import lru_cache
from uuid import UUID

import httpx
import jwt
from fastapi import Header, HTTPException
from jwt import PyJWKClient
from starlette.concurrency import run_in_threadpool

from .config import settings


@dataclass(frozen=True)
class Principal:
    subject: UUID
    token: str


@lru_cache
def jwks_client() -> PyJWKClient:
    return PyJWKClient(
        f"{settings().supabase_url}/auth/v1/.well-known/jwks.json",
        cache_jwk_set=True,
        lifespan=300,
        timeout=5,
    )


def decode_token(token: str) -> Principal:
    key = jwks_client().get_signing_key_from_jwt(token).key
    claims = jwt.decode(
        token,
        key,
        algorithms=["ES256", "RS256"],
        audience=settings().auth_audience,
        issuer=f"{settings().supabase_url}/auth/v1",
        options={"require": ["exp", "iat", "sub", "iss", "aud"]},
    )
    # No tenant or staff authorization is accepted from caller-controlled metadata.
    return Principal(subject=UUID(claims["sub"]), token=token)


async def optional_principal(authorization: str | None = Header(default=None)) -> Principal | None:
    if authorization is None:
        return None
    if not settings().auth_enabled:
        raise HTTPException(503, "Autenticación aún no configurada")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(401, "Token inválido")
    try:
        return await run_in_threadpool(decode_token, token)
    except (jwt.PyJWTError, ValueError):
        raise HTTPException(401, "Token inválido o vencido") from None


async def verified_email(principal: Principal) -> str:
    # Confirmation is checked server-side, never from editable user_metadata.
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(
            f"{settings().supabase_url}/auth/v1/user",
            headers={
                "apikey": settings().supabase_publishable_key,
                "Authorization": f"Bearer {principal.token}",
            },
        )
    if response.status_code != 200:
        raise HTTPException(401, "No se pudo verificar la identidad")
    user = response.json()
    if user.get("id") != str(principal.subject) or not user.get("email_confirmed_at"):
        raise HTTPException(403, "Verifica tu correo antes de vincular reservas")
    return user["email"]
