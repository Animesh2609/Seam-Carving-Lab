# Authentication setup for Streamlit Community Cloud

The public landing page works immediately, but sign-up and login require Supabase Auth.

1. Create a Supabase project at https://supabase.com/.
2. Under Authentication > Providers > Email, enable email sign-ups and confirmation. Configure production SMTP for reliable delivery to public users.
3. Find your project URL and public anon key (or compatible publishable key). Never put the service-role key in Streamlit.
4. In Streamlit Community Cloud, open your app settings > Secrets, and add:

```toml
SUPABASE_URL = "https://YOUR_PROJECT.supabase.co"
SUPABASE_ANON_KEY = "YOUR_PUBLIC_ANON_KEY"
```

5. Restart/redeploy the app. Users register with name, phone, email and password, confirm their email, then log in using email as the username.

## Security and scope

- **Passwords are not emailed**. Supabase handles password storage and email confirmation; users choose their own passwords. A reset-email form is available.
- Google/GitHub OAuth **is not implemented**; a provider-specific callback flow is needed. Streamlit accounts are not a general third-party authentication provider.
- Accounts persist in Supabase rather than Streamlit's ephemeral filesystem.
- Session state is browser-session scoped; users may need to log in after a refresh.
- This is an academic demonstration, not a security-audited production app.
- Contact details on the landing page are public.
