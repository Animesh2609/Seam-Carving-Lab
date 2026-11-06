"""Mocked Supabase email/password protocol tests; no external account needed."""
import unittest
import time
from auth_backend import AuthConfig, AuthError, SupabaseAuth

class FakeResponse:
    def __init__(self, payload, status=200):
        self.status_code = status
        self.content = b'{}'
        self.payload = payload
    def json(self):
        return self.payload

class FakeTransport:
    def __init__(self):
        self.calls = []
        self.responses = []
    def queue(self, payload, status=200):
        self.responses.append(FakeResponse(payload, status))
    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        return self.responses.pop(0)

def login_response():
    return {'access_token':'ACCESS','refresh_token':'REFRESH','expires_in':3600,
        'user':{'id':'11111111-1111-4111-8111-111111111111',
                'email':'test@example.com',
                'user_metadata':{'full_name':'Sample User','phone':'7607141408'}}}

class EmailAuthTests(unittest.TestCase):
    def setUp(self):
        self.transport = FakeTransport()
        self.auth = SupabaseAuth(AuthConfig('https://test.supabase.co','public_key',
            'https://sample.streamlit.app'), self.transport)

    def test_email_password_login(self):
        self.transport.queue(login_response())
        session = self.auth.sign_in('test@example.com','secret-password')
        self.assertEqual(session['name'],'Sample User')
        self.assertEqual(session['phone'],'7607141408')
        self.assertEqual(self.transport.calls[0][2]['params'],{'grant_type':'password'})
        self.assertEqual(self.transport.calls[0][1], 'https://test.supabase.co/auth/v1/token')

    def test_signup_records_metadata_and_redirect(self):
        self.transport.queue({'user':{'id':'new'}})
        self.auth.sign_up('Sample','7607141408','test@example.com','secretpassword')
        opts = self.transport.calls[0][2]
        self.assertEqual(opts['json']['data']['full_name'],'Sample')
        self.assertEqual(opts['params']['redirect_to'],'https://sample.streamlit.app')
        self.assertNotIn('refresh_token',opts['json'])

    def test_password_recovery_and_update(self):
        self.transport.queue({})
        self.auth.request_reset('test@example.com')
        self.assertTrue(self.transport.calls[0][1].endswith('/recover'))
        self.transport.queue({'access_token':'RECOVERY'})
        value = self.auth.verify_email_token('MYTOKEN','recovery')
        self.assertEqual(value['access_token'],'RECOVERY')
        self.transport.queue({'id':'new'})
        self.auth.update_password('RECOVERY','newlongpassword')
        self.assertEqual(self.transport.calls[-1][2]['headers']['Authorization'],'Bearer RECOVERY')

    def test_email_confirmation(self):
        self.transport.queue({'user':{'id':'new'}})
        self.auth.verify_email_token('HASH','email')
        self.assertEqual(self.transport.calls[0][2]['json']['type'],'email')

    def test_reject_invalid_reset_purpose_and_short_password(self):
        with self.assertRaises(AuthError): self.auth.verify_email_token('HASH','github')
        with self.assertRaises(AuthError): self.auth.update_password('SESSION','short')

    def test_refresh_session(self):
        session = self.auth.session(login_response())
        session['expires_at'] = time.time() - 1
        self.transport.queue(login_response())
        refreshed = self.auth.check_session(session)
        self.assertEqual(refreshed['access_token'],'ACCESS')
        self.assertEqual(self.transport.calls[0][2]['params'],{'grant_type':'refresh_token'})

    def test_update_profile(self):
        self.transport.queue({'user_metadata':{'full_name':'New Name'}})
        self.auth.update_profile('ACCESS','New Name','7654321090')
        self.assertEqual(self.transport.calls[0][2]['json']['data']['phone'],'7654321090')

    def test_invalid_configuration(self):
        with self.assertRaises(AuthError):
            SupabaseAuth(AuthConfig('','')).sign_in('test@example.com','pw')
        with self.assertRaises(AuthError):
            SupabaseAuth(AuthConfig('http://insecure.test','public'),self.transport).sign_in('x','y')

    def test_oauth_code_paths_are_not_exposed(self):
        self.assertFalse(hasattr(self.auth,'oauth_url'))
        self.assertFalse(hasattr(self.auth,'finish_oauth'))

if __name__ == '__main__': unittest.main()
