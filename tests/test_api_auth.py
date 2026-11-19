"""Supabase sign-in tokens: signing keys (JWKS), the legacy shared secret, and what is rejected."""

from __future__ import annotations

import time
import unittest
from types import SimpleNamespace

import jwt
from cryptography.hazmat.primitives.asymmetric import ec

from campusyamu.api.auth import AuthError, SupabaseAuth

URL = "https://proj.supabase.co"


class FakeJWKS:
    def __init__(self, public_key) -> None:
        self.public_key, self.calls = public_key, 0

    def get_signing_key_from_jwt(self, token):
        self.calls += 1
        return SimpleNamespace(key=self.public_key)


def claims(**over):
    return {"sub": "3f2a9c1e-7b4d-4e2a-9f1c-0a1b2c3d4e5f", "aud": "authenticated", "role": "authenticated",
            "iss": f"{URL}/auth/v1", "exp": int(time.time()) + 600, **over}


class SupabaseAuthTests(unittest.TestCase):
    def setUp(self) -> None:
        self.private = ec.generate_private_key(ec.SECP256R1())
        self.jwks = FakeJWKS(self.private.public_key())
        self.auth = SupabaseAuth(url=URL + "/", jwt_secret="", jwks_client=self.jwks)

    def es256(self, **over) -> str:
        return jwt.encode(claims(**over), self.private, algorithm="ES256", headers={"kid": "k1"})

    def test_signing_key_tokens(self) -> None:
        self.assertTrue(self.auth.enabled)
        self.assertEqual(self.auth.issuer, f"{URL}/auth/v1")                 # trailing slash trimmed
        self.assertEqual(self.auth.user_id(self.es256()), "3f2a9c1e-7b4d-4e2a-9f1c-0a1b2c3d4e5f")
        self.assertEqual(self.jwks.calls, 1)

    def test_rejected_tokens(self) -> None:
        other = ec.generate_private_key(ec.SECP256R1())
        cases = {
            "expired": self.es256(exp=int(time.time()) - 120),
            "another project": self.es256(iss="https://other.supabase.co/auth/v1"),
            "wrong audience": self.es256(aud="something-else"),
            "anon role": self.es256(role="anon"),
            "forged": jwt.encode(claims(), other, algorithm="ES256", headers={"kid": "k1"}),
            "alg none": jwt.encode(claims(), None, algorithm="none"),
            "garbage": "not.a.token",
        }
        for name, token in cases.items():
            with self.subTest(name), self.assertRaises(AuthError):
                self.auth.user_id(token)
        with self.assertRaisesRegex(AuthError, "expired"):
            self.auth.user_id(cases["expired"])

    def test_legacy_shared_secret(self) -> None:
        secret = "legacy-jwt-secret-of-the-project-0123456789"
        token = jwt.encode(claims(), secret, algorithm="HS256")
        with self.assertRaisesRegex(AuthError, "SUPABASE_JWT_SECRET"):
            self.auth.user_id(token)                                         # no secret configured
        self.assertEqual(SupabaseAuth(url=URL, jwt_secret=secret).user_id(token), claims()["sub"])
        wrong = jwt.encode(claims(), "another-secret-0123456789-0123456789", algorithm="HS256")
        with self.assertRaises(AuthError):
            SupabaseAuth(url=URL, jwt_secret=secret).user_id(wrong)

    def test_off_without_a_url(self) -> None:
        self.assertFalse(SupabaseAuth(url="").enabled)


if __name__ == "__main__":
    unittest.main()
