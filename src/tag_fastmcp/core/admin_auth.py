from __future__ import annotations

import base64
from dataclasses import dataclass
from typing import Any

import jwt
from jwt import InvalidTokenError
from pydantic import ValidationError

from tag_fastmcp.models.http_api import AdminUserContext
from tag_fastmcp.settings import AppSettings


@dataclass
class AdminAuthService:
    settings: AppSettings

    def resolve_request(
        self,
        *,
        authorization: str | None,
        dev_context_header: str | None,
    ) -> AdminUserContext:
        bearer_token = self._bearer_token(authorization)
        if bearer_token is not None:
            return self._decode_bearer_token(bearer_token)

        if self._effective_mode() == "dev_header":
            admin_context = self._decode_dev_header(dev_context_header)
            if admin_context is None:
                raise PermissionError("Valid x-admin-context header is required for admin routes in development mode.")
            return admin_context

        if dev_context_header:
            raise PermissionError("x-admin-context is only supported in development mode. Use Authorization: Bearer <token>.")

        raise PermissionError("Authorization: Bearer <token> is required for admin routes.")

    def _decode_bearer_token(self, token: str) -> AdminUserContext:
        verification_key = self.settings.admin_auth_jwt_public_key or self.settings.admin_auth_jwt_secret
        if not verification_key:
            raise PermissionError(
                "Admin JWT auth is not configured. Set TAG_FASTMCP_ADMIN_AUTH_JWT_SECRET or "
                "TAG_FASTMCP_ADMIN_AUTH_JWT_PUBLIC_KEY."
            )

        decode_kwargs: dict[str, Any] = {
            "algorithms": self.settings.admin_auth_jwt_algorithms,
            "options": {
                "verify_aud": self.settings.admin_auth_jwt_audience is not None,
                "verify_iss": self.settings.admin_auth_jwt_issuer is not None,
            },
        }
        if self.settings.admin_auth_jwt_audience is not None:
            decode_kwargs["audience"] = self.settings.admin_auth_jwt_audience
        if self.settings.admin_auth_jwt_issuer is not None:
            decode_kwargs["issuer"] = self.settings.admin_auth_jwt_issuer

        try:
            claims = jwt.decode(token, verification_key, **decode_kwargs)
        except InvalidTokenError as exc:
            raise PermissionError("Invalid admin bearer token.") from exc

        return self._claims_to_context(claims)

    def _claims_to_context(self, claims: dict[str, Any]) -> AdminUserContext:
        subject = self._claim_text(claims, self.settings.admin_auth_subject_claim)
        actor_id = self._claim_text(claims, self.settings.admin_auth_actor_id_claim) or subject
        role = self._claim_text(claims, self.settings.admin_auth_role_claim)
        scopes = self._claim_list(claims.get(self.settings.admin_auth_scopes_claim))
        if not scopes and self.settings.admin_auth_scopes_claim != "scopes":
            scopes = self._claim_list(claims.get("scopes"))

        if actor_id is None:
            raise PermissionError("Admin bearer token must include an actor identifier.")
        if role is None:
            raise PermissionError("Admin bearer token must include a supported role claim.")

        payload = {
            "actor_id": actor_id,
            "auth_subject": subject or actor_id,
            "tenant_id": self._claim_text(claims, self.settings.admin_auth_tenant_id_claim),
            "role": role,
            "auth_scopes": scopes,
            "allowed_app_ids": self._claim_list(claims.get(self.settings.admin_auth_allowed_app_ids_claim)),
        }
        try:
            return AdminUserContext.model_validate(payload)
        except ValidationError as exc:
            raise PermissionError("Admin bearer token contains invalid admin claims.") from exc

    def _effective_mode(self) -> str:
        if self.settings.admin_auth_mode != "auto":
            return self.settings.admin_auth_mode
        return "dev_header" if self.settings.environment == "development" else "jwt"

    @staticmethod
    def _decode_dev_header(raw_value: str | None) -> AdminUserContext | None:
        if not raw_value:
            return None
        try:
            decoded = base64.b64decode(raw_value).decode("utf-8")
            return AdminUserContext.model_validate_json(decoded)
        except Exception:
            return None

    @staticmethod
    def _bearer_token(raw_value: str | None) -> str | None:
        if raw_value is None:
            return None
        scheme, _, token = raw_value.strip().partition(" ")
        if scheme.lower() != "bearer" or not token.strip():
            raise PermissionError("Authorization header must use Bearer token auth.")
        return token.strip()

    @staticmethod
    def _claim_text(claims: dict[str, Any], claim_name: str) -> str | None:
        value = claims.get(claim_name)
        if value is None:
            return None
        normalized = str(value).strip()
        return normalized or None

    @staticmethod
    def _claim_list(raw_value: Any) -> list[str]:
        if raw_value is None:
            return []
        if isinstance(raw_value, str):
            normalized = raw_value.replace(",", " ")
            return [item for item in normalized.split() if item]
        if isinstance(raw_value, (list, tuple, set)):
            values: list[str] = []
            for item in raw_value:
                normalized = str(item).strip()
                if normalized:
                    values.append(normalized)
            return values
        normalized = str(raw_value).strip()
        return [normalized] if normalized else []
