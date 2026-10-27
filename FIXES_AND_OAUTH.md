# Full social login and recovery implementation

The previous build had disabled Google and GitHub placeholders and an email-only password recovery. This version implements:
- Clickable Google and GitHub OAuth URLs using Supabase Auth and PKCE authorization-code exchange.
- Encrypted, time-limited PKCE verifier in OAuth redirect state (Streamlit can open a new session on redirect).
- Callback handler, session verification, token refresh, and logout.
- Password recovery: custom email verification via `token_hash`, then a new-password screen and Supabase password update.
- Optional custom signup email confirmation callback.
- Name/phone completion after Google/GitHub login.
- Improved navigation spacing, preserves the complete image-processing workbench.

**Configure the providers and the Reset Password email template in Supabase before trying these flows.** See `AUTH_SETUP.md` for exact click-by-click instructions and TOML secrets.

This is an executable implementation but a real Google/GitHub/Supabase login requires external credentials and needs to be checked on the deployed site. There is no claim that actual provider authentication has been tested without those credentials.
