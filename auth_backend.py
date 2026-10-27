"""Supabase Auth REST integration for Streamlit.

OAuth uses PKCE with a short-lived encrypted callback payload, because a full-page
provider redirect creates a new Streamlit WebSocket session. Never put passwords,
access tokens, refresh tokens or plaintext PKCE verifiers in URL parameters.
"""
from __future__ import annotations

import base64
import hashlib
import json
import secrets
import time
from dataclasses import dataclass
from urllib.parse import urlencode, urlparse

import requests
from cryptography.fernet import Fernet, InvalidToken


class AuthError(Exception):
    """A user-facing authentication/configuration error."""


@dataclass(frozen=True)
class AuthConfig:
    url: str
    key: str
    app_url: str
    flow_secret: str = ""

    def valid_basic(self) -> bool:
        return bool(self.url and self.key)

    def valid_oauth(self) -> bool:
        return self.valid_basic() and bool(self.app_url and self.flow_secret)


class SupabaseAuth:
    def __init__(self, config: AuthConfig, transport=None):
        self.config = config
        self.transport = transport or requests

    def _base(self):
        if not self.config.valid_basic():
            raise AuthError("Set SUPABASE_URL and SUPABASE_ANON_KEY in Streamlit Secrets.")
        url = self.config.url.rstrip("/")
        parsed = urlparse(url)
        if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
            raise AuthError("SUPABASE_URL must be a valid HTTPS project URL.")
        return url + "/auth/v1"

    def _request(self, method, endpoint, *, data=None, access_token=None, params=None):
        base = self._base()
        headers = {"apikey": self.config.key, "Content-Type": "application/json"}
        if access_token:
            headers["Authorization"] = "Bearer " + access_token
        try:
            reply = self.transport.request(
                method, base + endpoint, headers=headers, json=data, params=params, timeout=20
            )
        except requests.RequestException as exc:
            raise AuthError("Cannot connect to Supabase. Check the project URL/network.") from exc
        try:
            payload = reply.json() if reply.content else {}
        except (ValueError, AttributeError):
            payload = {}
        if reply.status_code >= 400:
            reason = payload.get("msg") or payload.get("error_description") or payload.get("message") or payload.get("error")
            if not isinstance(reason, str):
                reason = f"Authentication server returned HTTP {reply.status_code}."
            raise AuthError(reason[:350])
        return payload

    def sign_up(self, name, phone, email, password):
        return self._request("POST", "/signup", data={
            "email": email, "password": password,
            "data": {"full_name": name, "phone": phone}
        }, params={"redirect_to": self.config.app_url} if self.config.app_url else None)

    def sign_in(self, email, password):
        reply = self._request("POST", "/token", params={"grant_type": "password"},
                              data={"email": email, "password": password})
        return self.session(reply)

    def session(self, payload):
        access = payload.get("access_token")
        user = payload.get("user")
        if not access or not isinstance(user, dict) or not user.get("id"):
            raise AuthError("Supabase did not return a valid authenticated session.")
        metadata = user.get("user_metadata") or {}
        return {
            "id": user["id"], "email": user.get("email", ""),
            "name": metadata.get("full_name") or metadata.get("name") or user.get("email", "User"),
            "phone": metadata.get("phone", ""),
            "access_token": access,
            "refresh_token": payload.get("refresh_token", ""),
            "expires_at": time.time() + int(payload.get("expires_in", 3600)),
            "validated_at": time.time(),
        }

    def check_session(self, session):
        if session["expires_at"] - time.time() < 60:
            if not session.get("refresh_token"):
                raise AuthError("Session expired; log in again.")
            reply = self._request("POST", "/token", params={"grant_type": "refresh_token"},
                                  data={"refresh_token": session["refresh_token"]})
            return self.session(reply)
        if time.time() - session.get("validated_at", 0) > 180:
            current = self._request("GET", "/user", access_token=session["access_token"])
            if current.get("id") != session.get("id"):
                raise AuthError("Session is no longer valid.")
            session["validated_at"] = time.time()
        return session

    def logout(self, session):
        try:
            self._request("POST", "/logout", access_token=session.get("access_token"))
        except AuthError:
            pass  # Always clear local session even if token already expired.

    def request_reset(self, email):
        return self._request("POST", "/recover", data={"email": email})

    def verify_email_token(self, token_hash, purpose):
        if purpose not in ("recovery", "email"):
            raise AuthError("Invalid email verification purpose.")
        if not token_hash or len(token_hash) > 1024:
            raise AuthError("Invalid confirmation link.")
        return self._request("POST", "/verify", data={"type": purpose, "token_hash": token_hash})

    def update_password(self, access_token, password):
        if len(password) < 10:
            raise AuthError("Password must contain at least 10 characters.")
        return self._request("PUT", "/user", data={"password": password}, access_token=access_token)

    def update_profile(self, access_token, name, phone):
        return self._request("PUT", "/user", data={"data": {
            "full_name": name, "phone": phone
        }}, access_token=access_token)

    def _cipher(self):
        if not self.config.flow_secret:
            raise AuthError("Set AUTH_FLOW_SECRET to a generated Fernet key in Streamlit Secrets.")
        try:
            return Fernet(self.config.flow_secret.encode("ascii"))
        except (ValueError, TypeError) as exc:
            raise AuthError("AUTH_FLOW_SECRET must be a valid Fernet key. See AUTH_SETUP.md.") from exc

    def oauth_url(self, provider):
        """Returns Supabase's provider URL and short-lived encrypted PKCE callback flow."""
        if provider not in ("google", "github"):
            raise AuthError("Unsupported social sign-in provider.")
        if not self.config.app_url:
            raise AuthError("Set APP_URL to your public .streamlit.app address first.")
        parsed = urlparse(self.config.app_url)
        if parsed.scheme != "https" or not parsed.netloc or parsed.query or parsed.fragment:
            raise AuthError("APP_URL must be the HTTPS app homepage without query parameters.")
        verifier = secrets.token_urlsafe(64)
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
        flow = self._cipher().encrypt(json.dumps({
            "verifier": verifier, "provider": provider, "app_url": self.config.app_url,
            "nonce": secrets.token_urlsafe(24)
        }).encode()).decode("ascii")
        redirect_to = self.config.app_url.rstrip("/") + "?flow=" + flow
        query = urlencode({
            "provider": provider, "redirect_to": redirect_to,
            "code_challenge": challenge, "code_challenge_method": "s256"
        })
        return self._base() + "/authorize?" + query

    def decode_oauth_flow(self, flow):
        if not flow or len(flow) > 4000:
            raise AuthError("Missing or invalid social sign-in state. Start again.")
        try:
            details = json.loads(self._cipher().decrypt(flow.encode(), ttl=600))
        except (InvalidToken, ValueError, TypeError, UnicodeDecodeError) as exc:
            raise AuthError("Social sign-in link expired or cannot be verified. Start again.") from exc
        if (details.get("provider") not in ("google", "github")
                or details.get("app_url") != self.config.app_url
                or not details.get("verifier")):
            raise AuthError("Social sign-in state did not match this app.")
        return details

    def finish_oauth(self, code, flow):
        details = self.decode_oauth_flow(flow)
        if not code or len(code) > 2000:
            raise AuthError("Missing authorization code. Start sign-in again.")
        result = self._request("POST", "/token", params={"grant_type": "pkce"},
                               data={"auth_code": code, "code_verifier": details["verifier"]})
        session = self.session(result)
        # Check identity server-side. We never trust user data from URL parameters.
        identity = self._request("GET", "/user", access_token=session["access_token"])
        if identity.get("id") != session["id"]:
            raise AuthError("Could not verify authenticated user identity.")
        return session
