"""Who is calling: Supabase Auth sign-in tokens.

When SUPABASE_URL is set, every /v1 endpoint except /v1/health needs

    Authorization: Bearer <access token>

where the token is the signed-in student's Supabase access token (the Supabase SDK in the web page or the
mobile app gives it and keeps it fresh). It is checked here, without a call to Supabase per request:

* signing keys (ES256 / RS256, the default for new projects): the public keys come from
  {SUPABASE_URL}/auth/v1/.well-known/jwks.json and are cached;
* the legacy shared secret (HS256): only if SUPABASE_JWT_SECRET is set.

Checked: signature, expiry, audience "authenticated", issuer {SUPABASE_URL}/auth/v1, role "authenticated".
The student's user id is the token's `sub`. Their name, for greetings, comes from the same verified token:
`user_metadata.full_name` (Google sign-in and email sign-up both set it), else `user_metadata.name`; the
greeting uses the first word of it (see `profile_from_claims`).

Without SUPABASE_URL the API is open (local development only): no sign-in, and the chat has no memory
(it uses the `history` the client sends).
"""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import sqlite3
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import jwt

from campusyamu.core.paths import PROJECT_ROOT

LEEWAY_SECONDS = 30
ASYMMETRIC = ("ES256", "RS256", "EdDSA")
LOCAL_ISSUER = "campusyamu-local"
TOKEN_TTL_SECONDS = 60 * 60 * 24 * 30  # 30 days


MAX_NAME_CHARS = 60


def profile_from_claims(claims: dict[str, Any]) -> dict[str, str | None]:
    """Display name and first name from verified token claims; None when the token carries no name.

    Supabase puts the provider profile in `user_metadata` (Google: full_name and name); local accounts put
    the sign-up name in `name`. Only the first word is used to greet: "Jaliya Nimantha" -> "Jaliya".
    The email is not used as a name.
    """

    meta = claims.get("user_metadata") if isinstance(claims.get("user_metadata"), dict) else {}
    for value in (meta.get("full_name"), meta.get("name"), claims.get("name")):
        full = " ".join(str(value or "").split())[:MAX_NAME_CHARS].strip()
        if full:
            return {"display_name": full, "first_name": full.split(" ")[0]}
    return {"display_name": None, "first_name": None}


class AuthError(Exception):
    """The request is not signed in (HTTP 401)."""


class AccountExistsError(Exception):
    """An account with that email already exists (HTTP 409)."""


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

        return str(self.claims(token)["sub"])

    def profile(self, token: str) -> dict[str, str | None]:
        """The signed-in student's name for greetings (see profile_from_claims), or AuthError."""

        return profile_from_claims(self.claims(token))

    def claims(self, token: str) -> dict[str, Any]:
        """The token's verified claims, or AuthError."""

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
        return claims


def _hash_password(password: str, salt: bytes | None = None) -> str:
    salt_bytes = salt or secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt_bytes, n=16384, r=8, p=1, dklen=32)
    return f"{salt_bytes.hex()}${digest.hex()}"


def _verify_password(password: str, stored: str) -> bool:
    try:
        salt_hex, digest_hex = stored.split("$", 1)
        expected = bytes.fromhex(digest_hex)
        actual = hashlib.scrypt(
            password.encode("utf-8"),
            salt=bytes.fromhex(salt_hex),
            n=16384,
            r=8,
            p=1,
            dklen=32,
        )
        return hmac.compare_digest(actual, expected)
    except Exception:
        return False


class LocalAuthStore:
    """SQLite-backed student accounts & HS256 JWTs when SUPABASE_URL is not configured."""

    def __init__(self, db_path: Path | None = None, secret: str | None = None) -> None:
        memory_dir = PROJECT_ROOT / "data" / "memory"
        memory_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = db_path or (memory_dir / "accounts.db")
        self._secret = secret or self._load_or_create_secret(memory_dir / ".jwt_secret")
        self._init_db()

    @staticmethod
    def _load_or_create_secret(secret_path: Path) -> str:
        env = os.getenv("LOCAL_AUTH_SECRET", "").strip()
        if env:
            return env
        if secret_path.is_file():
            saved = secret_path.read_text(encoding="utf-8").strip()
            if saved:
                return saved
        generated = secrets.token_urlsafe(48)
        secret_path.write_text(generated, encoding="utf-8")
        return generated

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS accounts (
                    id TEXT PRIMARY KEY,
                    email TEXT UNIQUE NOT NULL,
                    name TEXT NOT NULL DEFAULT '',
                    avatar TEXT NOT NULL DEFAULT 'fox',
                    avatar_locked INTEGER NOT NULL DEFAULT 0,
                    password_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            cols = {row["name"] for row in conn.execute("PRAGMA table_info(accounts)").fetchall()}
            if "avatar" not in cols:
                conn.execute("ALTER TABLE accounts ADD COLUMN avatar TEXT NOT NULL DEFAULT 'fox'")
            if "avatar_locked" not in cols:
                conn.execute("ALTER TABLE accounts ADD COLUMN avatar_locked INTEGER NOT NULL DEFAULT 0")

    def _issue_token(self, user_id: str, email: str, name: str) -> str:
        now = int(time.time())
        payload = {
            "sub": user_id,
            "email": email,
            "name": name,
            "aud": "authenticated",
            "role": "authenticated",
            "iss": LOCAL_ISSUER,
            "iat": now,
            "exp": now + TOKEN_TTL_SECONDS,
        }
        return jwt.encode(payload, self._secret, algorithm="HS256")

    def signup(self, email: str, password: str, name: str = "", avatar: str = "fox") -> dict[str, Any]:
        norm_email = email.strip().lower()
        clean_name = name.strip()
        clean_avatar = avatar.strip().lower() or "fox"
        if "@" not in norm_email or "." not in norm_email.split("@", 1)[1]:
            raise ValueError("Enter a valid email address")
        if len(password) < 6:
            raise ValueError("Password must be at least 6 characters")

        user_id = str(uuid.uuid4())
        created_at = datetime.now(timezone.utc).isoformat()
        pw_hash = _hash_password(password)

        try:
            with self._connect() as conn:
                conn.execute(
                    "INSERT INTO accounts (id, email, name, avatar, password_hash, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                    (user_id, norm_email, clean_name, clean_avatar, pw_hash, created_at),
                )
        except sqlite3.IntegrityError as exc:
            raise AccountExistsError("An account with this email already exists") from exc

        token = self._issue_token(user_id, norm_email, clean_name)
        return {
            "access_token": token,
            "token_type": "bearer",
            "user": {"id": user_id, "email": norm_email, "name": clean_name, "avatar": clean_avatar},
        }

    def signin(self, email: str, password: str) -> dict[str, Any]:
        norm_email = email.strip().lower()
        with self._connect() as conn:
            row = conn.execute(
                "SELECT id, email, name, avatar, password_hash FROM accounts WHERE email = ?",
                (norm_email,),
            ).fetchone()
        if row is None or not _verify_password(password, row["password_hash"]):
            raise AuthError("Invalid email or password")

        token = self._issue_token(row["id"], row["email"], row["name"])
        return {
            "access_token": token,
            "token_type": "bearer",
            "user": {"id": row["id"], "email": row["email"], "name": row["name"], "avatar": row["avatar"]},
        }

    def set_avatar(self, user_id: str, avatar: str) -> dict[str, Any]:
        clean_avatar = avatar.strip().lower() or "fox"
        with self._connect() as conn:
            row = conn.execute(
                "SELECT id, email, name, avatar, avatar_locked FROM accounts WHERE id = ?",
                (user_id,),
            ).fetchone()
            if row is None:
                raise AuthError("Account not found")
            if row["avatar_locked"]:
                raise AccountExistsError("Avatar has already been set and cannot be changed")
            conn.execute(
                "UPDATE accounts SET avatar = ?, avatar_locked = 1 WHERE id = ?",
                (clean_avatar, user_id),
            )
            return {"id": row["id"], "email": row["email"], "name": row["name"], "avatar": clean_avatar}

    def user_id(self, token: str) -> str:
        return str(self.claims(token)["sub"])

    def profile(self, token: str) -> dict[str, str | None]:
        return profile_from_claims(self.claims(token))

    def claims(self, token: str) -> dict[str, Any]:
        try:
            claims = jwt.decode(
                token,
                self._secret,
                algorithms=["HS256"],
                audience="authenticated",
                issuer=LOCAL_ISSUER,
                leeway=LEEWAY_SECONDS,
                options={"require": ["exp", "sub", "aud", "iss"]},
            )
        except jwt.ExpiredSignatureError as exc:
            raise AuthError("Sign-in expired: sign in again") from exc
        except jwt.PyJWTError as exc:
            raise AuthError("Invalid sign-in token") from exc
        if claims.get("role") != "authenticated" or not claims.get("sub"):
            raise AuthError("Sign in as a student")
        return claims
