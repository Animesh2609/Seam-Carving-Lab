# Email/password authentication setup (Google/GitHub not needed)

The app uses Supabase Auth for signup, login, confirmation and password reset.

1. In Supabase → Authentication → Sign In / Providers → Email, enable email signup and confirmation emails.
2. In Supabase → Authentication → URL Configuration, set Site URL to the public Streamlit root URL configured as `APP_URL` (e.g. `https://your-app.streamlit.app`). Add the app URL to Redirect URLs.
3. In Supabase → Authentication → Email Templates → Confirm Signup, use a confirmation link that carries the one-time token hash in the query string, so Streamlit can read it. Example custom HTML snippet:

```html
<p><a href="{{ .SiteURL }}?auth_action=confirm&amp;token_hash={{ .TokenHash }}">Confirm email</a></p>
```

4. Under the Reset Password email template, use:

```html
<p><a href="{{ .SiteURL }}?auth_action=reset&amp;token_hash={{ .TokenHash }}">Set a new password</a></p>
```

5. Keep the rest of your preferred email templates. After editing templates, test with a NEW email link; older links may still point to localhost or use a browser fragment.
6. For public registration to arbitrary email domains, configure a proper SMTP provider in Supabase. The restricted default sender is intended only for initial testing.
7. Existing Google/GitHub-only accounts may not have an email/password credential. If a user wants to keep such an account, try Supabase's password-reset process for its verified email, then use email login.

**Security:** Never send passwords over email, never commit private configuration files, and never use `service_role` credentials for a publicly reachable Streamlit app.
