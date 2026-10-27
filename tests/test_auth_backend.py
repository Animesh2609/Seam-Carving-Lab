"""Offline tests for the Supabase REST protocol and encrypted PKCE flow."""
import base64
import json
import time
import unittest
from unittest.mock import Mock
from urllib.parse import parse_qs, urlparse

from cryptography.fernet import Fernet
from auth_backend import AuthConfig, AuthError, SupabaseAuth


class FakeHTTP:
    def __init__(self):
        self.calls = []
        self.responses = []

    def queue(self, data, status=200):
        self.responses.append((data, status))

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        assert self.responses, "Unexpected HTTP request"
        data, status = self.responses.pop(0)
        reply = Mock()
        reply.status_code = status
        reply.content = json.dumps(data).encode()
        reply.json.return_value = data
        return reply


def token_response(user_id="user123", email="test@example.com"):
    return {"access_token":"ACCESS_TOKEN", "refresh_token":"REFRESH_TOKEN", "expires_in":3600,
            "user":{"id":user_id,"email":email,"user_metadata":{"full_name":"Example User","phone":"9876543210"}}}


class AuthenticationTests(unittest.TestCase):
    def setUp(self):
        self.transport = FakeHTTP()
        self.key = Fernet.generate_key().decode()
        self.url = "https://myapp.streamlit.app"
        config = AuthConfig("https://myproject.supabase.co", "sb_publishable_test", self.url, self.key)
        self.auth = SupabaseAuth(config, transport=self.transport)

    def test_login_extracts_user_and_keeps_access_token_server_side(self):
        self.transport.queue(token_response())
        session = self.auth.sign_in("test@example.com", "mypassphrase")
        self.assertEqual(session["id"], "user123")
        self.assertEqual(session["access_token"], "ACCESS_TOKEN")
        self.assertTrue(self.transport.calls[0][1].endswith("/token"))
        self.assertEqual(self.transport.calls[0][2]["params"], {"grant_type": "password"})

    def test_google_and_github_have_distinct_encrypted_pkce_links(self):
        for provider in ("google", "github"):
            with self.subTest(provider=provider):
                uri = self.auth.oauth_url(provider)
                parsed = urlparse(uri)
                query = parse_qs(parsed.query)
                self.assertEqual(query["provider"], [provider])
                self.assertEqual(query["code_challenge_method"], ["s256"])
                self.assertTrue(query["redirect_to"][0].startswith(self.url + "?flow="))
                flow = parse_qs(urlparse(query["redirect_to"][0]).query)["flow"][0]
                details = self.auth.decode_oauth_flow(flow)
                self.assertEqual(details["provider"], provider)
                self.assertNotIn(details["verifier"], uri)
                self.assertEqual(len(query["code_challenge"][0]), 43)

    def test_oauth_exchanges_code_and_validates_identity(self):
        uri = self.auth.oauth_url("google")
        q = parse_qs(urlparse(uri).query)
        flow = parse_qs(urlparse(q["redirect_to"][0]).query)["flow"][0]
        self.transport.queue(token_response())
        self.transport.queue({"id": "user123", "email": "test@example.com"})
        session = self.auth.finish_oauth("AUTHCODE", flow)
        self.assertEqual(session["id"], "user123")
        args = self.transport.calls[0]
        self.assertEqual(args[2]["params"], {"grant_type": "pkce"})
        self.assertEqual(args[2]["json"]["auth_code"], "AUTHCODE")
        self.assertEqual(self.transport.calls[1][0], "GET")

    def test_mismatch_is_rejected(self):
        flow = parse_qs(urlparse(parse_qs(urlparse(self.auth.oauth_url("github")).query)["redirect_to"][0]).query)["flow"][0]
        self.transport.queue(token_response())
        self.transport.queue({"id": "wrong_user"})
        with self.assertRaisesRegex(AuthError, "identity"):
            self.auth.finish_oauth("CODE", flow)

    def test_tampered_and_expired_flow_rejected(self):
        flow = parse_qs(urlparse(parse_qs(urlparse(self.auth.oauth_url("google")).query)["redirect_to"][0]).query)["flow"][0]
        with self.assertRaises(AuthError):
            self.auth.decode_oauth_flow("bad." + flow)
        old = Fernet(self.key.encode()).encrypt_at_time(b'{"provider":"google","verifier":"abc","app_url":"https://myapp.streamlit.app"}', int(time.time()) - 1800).decode()
        with self.assertRaises(AuthError):
            self.auth.decode_oauth_flow(old)

    def test_password_reset_verification_and_update(self):
        self.transport.queue({})
        self.auth.request_reset("test@example.com")
        self.assertEqual(self.transport.calls[0][1], "https://myproject.supabase.co/auth/v1/recover")
        self.transport.queue(token_response())
        payload = self.auth.verify_email_token("HASH123", "recovery")
        self.assertEqual(self.transport.calls[1][2]["json"], {"type":"recovery", "token_hash":"HASH123"})
        self.transport.queue({"id":"user123"})
        self.auth.update_password(payload["access_token"], "newlongpassword")
        self.assertEqual(self.transport.calls[2][0], "PUT")
        self.assertEqual(self.transport.calls[2][2]["json"], {"password": "newlongpassword"})
        self.assertEqual(self.transport.calls[2][2]["headers"]["Authorization"], "Bearer ACCESS_TOKEN")

    def test_profile_completion_updates_metadata(self):
        self.transport.queue({"id": "user123"})
        self.auth.update_profile("ACCESS_TOKEN", "Some Name", "7607141408")
        self.assertEqual(self.transport.calls[0][2]["json"]["data"]["full_name"], "Some Name")

    def test_session_refresh_and_server_side_recheck(self):
        session = self.auth.session(token_response())
        session["expires_at"] = time.time() - 2
        self.transport.queue(token_response())
        renewed = self.auth.check_session(session)
        self.assertGreater(renewed["expires_at"], time.time())
        self.assertEqual(self.transport.calls[0][2]["params"], {"grant_type": "refresh_token"})

    def test_missing_configuration_and_insecure_redirect_rejected(self):
        with self.assertRaises(AuthError):
            SupabaseAuth(AuthConfig("", "", "")).sign_in("x@y.z", "pwd")
        with self.assertRaises(AuthError):
            SupabaseAuth(AuthConfig("https://project.supabase.co", "public", "http://not-https.example", self.key)).oauth_url("google")


if __name__ == "__main__":
    unittest.main()
