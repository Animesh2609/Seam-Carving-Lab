"""Supabase email/password authentication only (no Google/GitHub OAuth).

Sessions are stored in Streamlit session_state (not a permanent browser cookie).
User-owned image history is protected by Supabase JWT and Row Level Security.
"""
from __future__ import annotations
import time
from dataclasses import dataclass
from urllib.parse import urlparse
import requests

class AuthError(Exception):
    """A user-facing authentication or configuration error."""

@dataclass(frozen=True)
class AuthConfig:
    url: str
    key: str
    app_url: str = ""

    def valid_basic(self) -> bool:
        return bool(self.url and self.key)

class SupabaseAuth:
    def __init__(self, config: AuthConfig, transport=None):
        self.config = config
        self.transport = transport or requests

    def _base(self):
        if not self.config.valid_basic():
            raise AuthError('Set SUPABASE_URL and SUPABASE_ANON_KEY in Streamlit Secrets.')
        url = self.config.url.rstrip('/')
        parsed = urlparse(url)
        if parsed.scheme != 'https' or not parsed.netloc or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise AuthError('SUPABASE_URL must be an HTTPS Supabase project URL.')
        return url + '/auth/v1'

    def _request(self, method, endpoint, *, data=None, access_token=None, params=None):
        headers = {'apikey': self.config.key, 'Content-Type': 'application/json'}
        if access_token:
            headers['Authorization'] = 'Bearer ' + access_token
        try:
            response = self.transport.request(method, self._base() + endpoint,
                headers=headers, json=data, params=params, timeout=20)
        except requests.RequestException as exc:
            raise AuthError('Cannot connect to Supabase. Check the project URL/network.') from exc
        try:
            payload = response.json() if response.content else {}
        except (ValueError, AttributeError):
            payload = {}
        if response.status_code >= 400:
            reason = payload.get('msg') or payload.get('error_description') or payload.get('message') or payload.get('error')
            if not isinstance(reason, str):
                reason = f'Authentication failed (HTTP {response.status_code}).'
            raise AuthError(reason[:350])
        return payload

    def sign_up(self, name, phone, email, password):
        params = {'redirect_to': self.config.app_url} if self.config.app_url else None
        return self._request('POST','/signup', data={'email':email, 'password':password,
            'data':{'full_name':name,'phone':phone}},params=params)

    def sign_in(self, email, password):
        result = self._request('POST','/token',params={'grant_type':'password'},
            data={'email':email,'password':password})
        return self.session(result)

    def session(self, payload):
        access = payload.get('access_token')
        user = payload.get('user')
        if not access or not isinstance(user, dict) or not user.get('id'):
            raise AuthError('Supabase did not return a valid authenticated session.')
        metadata = user.get('user_metadata') or {}
        now = time.time()
        return {'id': user['id'], 'email':user.get('email',''),
            'name':metadata.get('full_name') or metadata.get('name') or user.get('email','User'),
            'phone': metadata.get('phone',''),
            'access_token':access, 'refresh_token':payload.get('refresh_token',''),
            'expires_at':now+int(payload.get('expires_in',3600)), 'validated_at':now}

    def check_session(self, session):
        if session['expires_at']-time.time()<60:
            if not session.get('refresh_token'):
                raise AuthError('Your session expired. Please log in again.')
            result = self._request('POST','/token',params={'grant_type':'refresh_token'},
                data={'refresh_token':session['refresh_token']})
            return self.session(result)
        if time.time()-session.get('validated_at',0)>180:
            current = self._request('GET','/user',access_token=session['access_token'])
            if current.get('id')!=session.get('id'):
                raise AuthError('The session is no longer valid.')
            metadata = current.get('user_metadata') or {}
            session['name'] = metadata.get('full_name') or session.get('name','')
            session['phone'] = metadata.get('phone') or session.get('phone','')
            session['validated_at']=time.time()
        return session

    def logout(self, session):
        try:
            self._request('POST','/logout',access_token=session.get('access_token'))
        except AuthError:
            pass  # Clear the local session even if the server token expired.

    def request_reset(self,email):
        return self._request('POST','/recover',data={'email':email})

    def verify_email_token(self,token_hash,purpose):
        if purpose not in ('recovery','email'):
            raise AuthError('Invalid email verification purpose.')
        if not token_hash or len(token_hash)>1024:
            raise AuthError('Invalid or missing email token.')
        return self._request('POST','/verify',data={'type':purpose,'token_hash':token_hash})

    def update_password(self,access_token,password):
        if len(password)<10:
            raise AuthError('Password must contain at least 10 characters.')
        return self._request('PUT','/user', data={'password':password},access_token=access_token)

    def update_profile(self,access_token,name,phone):
        return self._request('PUT','/user',data={'data':{'full_name':name,'phone':phone}},
            access_token=access_token)
