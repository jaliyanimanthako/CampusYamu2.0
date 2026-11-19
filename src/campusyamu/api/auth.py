"""Who is calling: Supabase Auth sign-in tokens.

When SUPABASE_URL is set, every /v1 endpoint except /v1/health needs

    Authorization: Bearer <access token>

where the token is the signed-in student's Supabase access token (the Supabase SDK in the web page or the
mobile app gives it and keeps it fresh). It is checked here, without a call to Supabase per request:

* signing keys (ES256 / RS256, the default for new projects): the public keys come from
  {SUPABASE_URL}/auth/v1/.well-known/jwks.json and are cached;
* the legacy shared secret (HS256): only if SUPABASE_JWT_SECRET is set.

Checked: signature, expiry, audience "authenticated", issuer {SUPABASE_URL}/auth/v1, role "authenticated".
The student's user id is the token's `sub`.

Without SUPABASE_URL the API is open (local development only): no sign-in, and the chat has no memory
(it uses the `history` the client sends).
"""

from __future__ import annotations

import os
from typing import Any

import jwt

LEEWAY_SECONDS = 30
ASYMMETRIC = ("ES256", "RS256", "EdDSA")


class AuthError(Exception):
    """The request is not signed in (HTTP 401)."""


class SupabaseAuth:
    def __init__(self, url: str | None = None, jwt_secret: str | None = None, jwks_client: Any = None) -> None:
        self.url = (os.getenv("SUPABASE_URL", "") if url is None else url).strip().rstrip("/")
        self.secret = os.getenv("SUPABASE_JWT_SECRET") if jwt_secret is None else jwt_secret
        self._jwks = jwks_client

    @property
    def enabled(self) -> bool:
        return bool(self.url)

    @property
    def issuer(self) -> str:
        return f"{self.url}/auth/v1"

    def jwks(self) -> Any:
        if self._jwks is None:
            self._jwks = jwt.PyJWKClient(f"{self.issuer}/.well-known/jwks.json", cache_keys=True, lifespan=3600,
                                         timeout=10)
        return self._jwks

    def user_id(self, token: str) -> str:
        """The signed-in student's id, or AuthError."""

        try:
            alg = jwt.get_unverified_header(token).get("alg")
            if alg == "HS256":
                if not self.secret:
                    raise AuthError("This sign-in token type needs SUPABASE_JWT_SECRET on the server")
                key: Any = self.secret
            elif alg in ASYMMETRIC:
                key = self.jwks().get_signing_key_from_jwt(token).key
            else:
                raise AuthError("Invalid sign-in token")
            claims = jwt.decode(token, key, algorithms=[alg], audience="authenticated", issuer=self.issuer,
                                leeway=LEEWAY_SECONDS, options={"require": ["exp", "sub", "aud", "iss"]})
        except jwt.ExpiredSignatureError as exc:
            raise AuthError("Sign-in expired: refresh the session and try again") from exc
        except jwt.PyJWKClientConnectionError as exc:
            raise AuthError("Could not fetch the Supabase signing keys; try again") from exc
        except jwt.PyJWTError as exc:
            raise AuthError("Invalid sign-in token") from exc
        if claims.get("role") != "authenticated" or not claims.get("sub"):
            raise AuthError("Sign in as a student")
        return str(claims["sub"])
