# Quick deployment checklist — Google, GitHub & password reset

**Important:** Running this ZIP does not automatically enable Google/GitHub provider accounts. Your Google, GitHub and Supabase dashboard settings must match the deployed app URL. Read `AUTH_SETUP.md` for every setting.

1. Replace the previous project's files on GitHub with these files (especially `app.py`, `auth_ui.py`, new `auth_backend.py`, `requirements.txt`, `AUTH_SETUP.md`). Commit/push.
2. Supabase → Authentication → URL Configuration: Site URL = exact public `.streamlit.app` URL. Allow that exact URL and `YOUR_APP_URL?flow=**` for OAuth callbacks.
3. Streamlit Cloud → Secrets: `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `APP_URL`, `AUTH_FLOW_SECRET` (TOML format). Generate Fernet key as described in `AUTH_SETUP.md`.
4. Google Cloud Console: create an OAuth Web client; callback = `https://PROJECT_REF.supabase.co/auth/v1/callback`. Enable Google in Supabase Providers with its Google Client ID/Secret.
5. GitHub Settings → Developer settings → OAuth Apps: callback = same Supabase Auth callback. Enable GitHub in Supabase Providers with its GitHub Client ID/Secret.
6. Supabase → Authentication → Email Templates → **Reset Password**: replace the link using the template in `AUTH_SETUP.md` (uses `token_hash`, **not** the default fragment link). Optionally customize Confirm Signup similarly.
7. Supabase: configure SMTP before public signups from arbitrary email addresses.
8. Test Google sign-in, GitHub sign-in, email confirmation, password reset, logout, and the image editor on the deployed app.

If the OAuth callback lands on the home page instead of the **Complete social sign-in** screen, your Supabase Redirect URL allow list is likely not matching the `?flow=` callback URL. Verify the App URL and allow-list pattern. If Google/GitHub gives a callback mismatch, the provider callback must be the **Supabase** `/auth/v1/callback` address, not the Streamlit URL.

Users authenticate with their email/password or Google/GitHub accounts. There is no login using Streamlit user accounts.
