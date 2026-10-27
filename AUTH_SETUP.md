# Seam Carving Lab: complete public authentication setup

This build implements **email/password signup and login, Google OAuth login, GitHub OAuth login, email verification, password recovery and password updates, and profile completion after social login**. It requires you, as the site owner, to set up the external OAuth providers and email templates in Supabase. Without these settings, the corresponding flows will not succeed.

## 1. Create or open Supabase project

Go to https://supabase.com/dashboard. In **Authentication > Providers > Email**, enable email signups and email confirmation.

In **Authentication > URL Configuration**:

- Set **Site URL** to your actual public URL, e.g. `https://YOUR-APP.streamlit.app` (NOT `localhost`).
- Add that exact public URL in **Redirect URLs**.
- For this Streamlit PKCE integration also add the narrow allow-list pattern: `https://YOUR-APP.streamlit.app?flow=**`. This allows only the app hostname and its encrypted OAuth callback-state query. Supabase may otherwise silently fall back to Site URL, losing the PKCE verifier.

For local development, if testing local callbacks, add the corresponding localhost URL and localhost query allow-list explicitly. Use HTTPS in production.

## 2. Streamlit Community Cloud secrets (required)

App settings > **Secrets** uses TOML. Paste with **real** values:

```toml
SUPABASE_URL = "https://YOUR_PROJECT_REF.supabase.co"
SUPABASE_ANON_KEY = "sb_publishable_YOUR_PUBLIC_KEY"
APP_URL = "https://YOUR-APP.streamlit.app"
AUTH_FLOW_SECRET = "YOUR_GENERATED_FERNET_KEY"
```

`SUPABASE_ANON_KEY` is the name the project expects, even when using a newer *publishable* key. NEVER paste Supabase `service_role`, `sb_secret_...`, Google or GitHub client secrets here. Those stay in their respective provider configuration screens in Supabase/Google/GitHub.

To create `AUTH_FLOW_SECRET`, on your laptop after installing requirements run:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Copy the resulting key into Streamlit Secrets. This key encrypts a short-lived OAuth PKCE verifier for provider redirects, because a redirect opens a fresh Streamlit session. Keep it private and stable. Rotating it invalidates in-progress sign-in links (fine).

## 3. Configure Google sign-in

1. Go to https://console.cloud.google.com/ and create/select a project.
2. Open **Google Auth Platform** (or APIs & Services > OAuth consent screen). Set app details. In test mode, add the Google accounts that should be allowed to sign in.
3. Create an **OAuth 2.0 Client ID**, type **Web application**.
4. Under **Authorized redirect URIs**, enter this EXACT callback URL (replace ref):
   `https://YOUR_PROJECT_REF.supabase.co/auth/v1/callback`
5. Copy the **Google Client ID and Client Secret**.
6. In **Supabase > Authentication > Sign In / Providers > Google**, enable the provider, paste the Client ID and Secret, and save.

Do NOT set the Google callback to the `.streamlit.app` URL; Google must redirect to Supabase first. Supabase then redirects to your Streamlit `APP_URL` with an authorization code.

Official instructions: https://supabase.com/docs/guides/auth/social-login/auth-google

## 4. Configure GitHub sign-in

1. GitHub > **Settings > Developer settings > OAuth Apps > New OAuth App**.
2. **Application name:** Seam Carving Lab.
3. **Homepage URL:** `https://YOUR-APP.streamlit.app`.
4. **Authorization callback URL:** `https://YOUR_PROJECT_REF.supabase.co/auth/v1/callback`.
5. Register the app and generate/copy its **Client ID** and **Client Secret**.
6. In **Supabase > Authentication > Sign In / Providers > GitHub**, enable the provider, paste the GitHub Client ID and Secret and save.

Official instructions: https://supabase.com/docs/guides/auth/social-login/auth-github

## 5. REQUIRED: fix the password reset email template

**Supabase > Authentication > Email Templates > Reset Password**. Keep your existing branding if desired, but point the action link to Streamlit and include `{{ .TokenHash }}`:

```html
<h2>Reset your Seam Carving Lab password</h2>
<p>Click below to open the password-reset screen.</p>
<p><a href="{{ .SiteURL }}?auth_action=reset&amp;token_hash={{ .TokenHash }}">Choose a new password</a></p>
<p>If you did not request this, ignore this email.</p>
```

Why? Supabase's default `{{ .ConfirmationURL }}` sends authentication tokens in a `#fragment`. Streamlit's Python server cannot read browser URL fragments. Instead, our code takes `token_hash` as a one-time email link, calls Supabase `/auth/v1/verify` **only after the user clicks the button on the page**, then uses the resulting recovery session to update their password via `/auth/v1/user`. The extra click avoids link-prefetch scanners consuming verification tokens.

**Optional, recommended:** similarly customize **Confirm Signup** email template:

```html
<h2>Confirm your Seam Carving Lab account</h2>
<p><a href="{{ .SiteURL }}?auth_action=confirm&amp;token_hash={{ .TokenHash }}">Confirm email address</a></p>
```

This routes confirmation through the project's confirmation screen. You can also leave the standard confirmation email unchanged: Supabase will confirm the user first, then redirect back to the public Site URL. After that, the user logs in manually. Do NOT set Site URL to localhost.

If you use a default Supabase email sender, it is severely restricted for public sign-ups. Configure production SMTP under Supabase Auth before inviting arbitrary people.

Official template docs: https://supabase.com/docs/guides/auth/auth-email-templates

## 6. Deploy files from the ZIP

Upload **contents** of `SeamCarvingLab_Complete/` into your GitHub repository root, replacing existing code. The GitHub root must contain `app.py`, `auth_ui.py`, `auth_backend.py`, `requirements.txt`, etc. Do not commit `.streamlit/secrets.toml`. Streamlit Cloud should redeploy when you push.

For local run:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m streamlit run app.py
```

On Streamlit Cloud choose Python 3.12 if your deployment UI offers it (Python 3.14 may have package compatibility issues with optional ML dependencies).

## 7. Validate each flow

1. **Email signup**: create a user, open their confirmation email, click the confirmation button on the Streamlit site, log in.
2. **Forgot password**: request a reset email, click its link, press **Verify password-reset link**, enter a new password, log in with that new password. The old password should no longer work.
3. **Google**: choose Google, sign in on Google, return to the Streamlit callback tab and press **Finish secure sign-in**, fill your phone if needed, enter the workbench.
4. **GitHub**: repeat using GitHub.
5. **Sign out**: click Sign out and verify that the workbench is no longer accessible.
6. **Image-processing regression**: upload an image and check energy-map, carving, object removal, etc.

## Limitations and security notes

- OAuth uses short-lived PKCE codes; the verifier is encrypted with a server secret in the redirect query. This avoids storing bearer access tokens or raw verifiers in URLs. A full security review is still required before using this as a commercial identity product.
- The OAuth callback asks the user to explicitly finish sign-in instead of silently accepting a callback from a link they did not initiate.
- Login sessions live in Streamlit session state, so a page refresh can require signing in again.
- Supabase accounts are persistent, but the temporary Streamlit session isn't.
- Passwords are never emailed or stored by this application; Supabase manages credentials.
- There is **no** third-party Streamlit-account OAuth login: a Streamlit account is not a supported identity provider for this app.
- Without the real Supabase/Google/GitHub credentials, the provider connection cannot be tested end to end in a local ZIP. The automated tests cover mocked REST exchanges, PKCE state, password update, and algorithm behaviour.
