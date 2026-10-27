"""Streamlit landing page and complete Supabase Auth UI.

The actual image-processing code is intentionally kept outside this module.
"""
from __future__ import annotations
import os
import re

import streamlit as st
from auth_backend import AuthConfig, AuthError, SupabaseAuth

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_RE = re.compile(r"^[+0-9()\s-]{7,20}$")


def setting(name):
    value = os.getenv(name)
    if value:
        return value
    try:
        return st.secrets.get(name, "")
    except (FileNotFoundError, KeyError):
        return ""


def auth_client():
    return SupabaseAuth(AuthConfig(
        url=setting("SUPABASE_URL"), key=setting("SUPABASE_ANON_KEY"),
        app_url=setting("APP_URL").rstrip("/"), flow_secret=setting("AUTH_FLOW_SECRET")
    ))


def configured():
    return auth_client().config.valid_basic()


def _clean_auth_params():
    for param in ("code", "flow", "error", "error_description", "auth_action", "token_hash"):
        if param in st.query_params:
            del st.query_params[param]


def clear_session():
    account = st.session_state.get("account")
    if account:
        auth_client().logout(account)
    for key in ("account", "result", "object_result", "multi_result", "semantic", "semantic_selection", "reset_access_token"):
        st.session_state.pop(key, None)
    _clean_auth_params()
    st.session_state["page"] = "home"
    st.rerun()


def nav():
    a, b = st.columns([5, 1.5], vertical_alignment="center")
    with a:
        st.markdown("### ✂️ Seam Carving Lab")
    with b:
        if st.session_state.get("account"):
            if st.button("Sign out", key="nav_sign_out", use_container_width=True):
                clear_session()
        elif st.session_state.get("page") == "home":
            if st.button("Sign in", key="nav_sign_in", type="primary", use_container_width=True):
                st.session_state["page"] = "auth"
                st.rerun()


def landing():
    nav()
    st.markdown('''<section class="hero"><div class="eyebrow">CONTENT-AWARE IMAGE EDITING</div>
        <h1>Resize smarter.<br>Preserve what matters.</h1>
        <p>Explore seam carving, object removal, energy maps, semantic protection
        and multi-size image exports in a single interactive workbench.</p></section>''', unsafe_allow_html=True)
    one, two, three = st.columns(3)
    with one:
        st.subheader("🖼️ Smart resizing")
        st.write("Remove or insert low-energy seams and compare with conventional resizing.")
    with two:
        st.subheader("🧩 Object removal")
        st.write("Mark unwanted areas and guide connected seams through them.")
    with three:
        st.subheader("🔎 Explore the method")
        st.write("Visualize pixel energy, optimal seams and output comparisons.")
    st.divider()
    st.subheader("How it works")
    st.write("**Sign up → Upload an image → Configure a method → Compare and download.**")
    if st.button("Get started", type="primary"):
        st.session_state["page"] = "auth"
        st.rerun()
    st.divider()
    st.subheader("About the team")
    st.markdown("**Animesh Singh (2026H1120144P)** — Developer and project author")
    st.markdown("**Email:** [animeshsingh1403@gmail.com](mailto:animeshsingh1403@gmail.com)")
    st.markdown("**Mobile:** [7607141408](tel:7607141408)")
    st.caption("Research basis: Avidan & Shamir, Seam Carving for Content-Aware Image Resizing (2007).")


def _enter_app(session):
    st.session_state["account"] = session
    st.session_state["page"] = "studio" if session.get("phone") else "profile"
    st.rerun()


def auth_page():
    nav()
    st.title("Sign in to Seam Carving Lab")
    st.write("Create an account, or log in to open the image-processing workbench.")
    if st.session_state.pop("auth_notice", None):
        st.success("Your email has been confirmed. You can now log in.")
    if st.session_state.pop("password_changed_notice", None):
        st.success("Password updated successfully. Log in using your new password.")
    if not configured():
        st.warning("Ask the site owner to configure Supabase in Streamlit App Settings → Secrets.")

    signup_tab, login_tab = st.tabs(["Create account", "Existing account"])
    with signup_tab:
        with st.form("auth_signup"):
            name = st.text_input("Full name", key="signup_name")
            phone = st.text_input("Phone number", key="signup_phone")
            email = st.text_input("Email address", key="signup_email")
            password = st.text_input("Choose password", type="password", key="signup_pw")
            again = st.text_input("Confirm password", type="password", key="signup_confirm")
            submitted = st.form_submit_button("Create account", type="primary", disabled=not configured())
        if submitted:
            if not name.strip() or not PHONE_RE.fullmatch(phone.strip()):
                st.error("Enter a name and valid phone number.")
            elif not EMAIL_RE.fullmatch(email.strip()):
                st.error("Enter a valid email address.")
            elif len(password) < 10 or password != again:
                st.error("Passwords must match and contain at least 10 characters.")
            else:
                try:
                    auth_client().sign_up(name.strip(), phone.strip(), email.strip().lower(), password)
                    st.success("Registration submitted. Check your inbox to confirm your email, then log in.")
                    st.caption("Your email is the username. Passwords are NEVER sent by email.")
                except AuthError as exc:
                    st.error(str(exc))

    with login_tab:
        with st.form("auth_login"):
            email = st.text_input("Username (email address)", key="login_email")
            password = st.text_input("Password", type="password", key="login_pw")
            login = st.form_submit_button("Log in", type="primary", disabled=not configured())
        if login:
            try:
                _enter_app(auth_client().sign_in(email.strip().lower(), password))
            except AuthError as exc:
                st.error(str(exc))
        with st.expander("Forgot password?"):
            with st.form("request_password_reset"):
                recovery_email = st.text_input("Account email", key="reset_email")
                send = st.form_submit_button("Send password-reset email", disabled=not configured())
            if send:
                if not EMAIL_RE.fullmatch(recovery_email.strip()):
                    st.error("Enter a valid email address.")
                else:
                    try:
                        auth_client().request_reset(recovery_email.strip().lower())
                        st.success("If the account exists, a reset message will arrive shortly.")
                        st.caption("Use the latest email. The reset email template must point back to this website.")
                    except AuthError as exc:
                        st.error(str(exc))

    st.divider()
    st.subheader("Or continue with")
    if not setting("APP_URL") or not setting("AUTH_FLOW_SECRET") or not configured():
        st.info("To activate Google/GitHub sign-in, set APP_URL and AUTH_FLOW_SECRET in Streamlit Secrets.")
    left, right = st.columns(2)
    for column, provider, label in ((left, "google", "Continue with Google"),
                                    (right, "github", "Continue with GitHub")):
        with column:
            try:
                url = auth_client().oauth_url(provider)
                # Opens a new browser tab. Once the provider redirects back, the
                # app exchanges the one-use PKCE code in that tab.
                st.link_button(label, url, use_container_width=True)
            except AuthError:
                st.button(label, disabled=True, use_container_width=True, key=f"{provider}_unavailable")
    st.caption("Google and GitHub accounts are verified through Supabase. The site owner must enable both providers in Supabase first. Streamlit accounts cannot be used as a third-party sign-in provider.")
    if st.button("← Back to home", key="back_to_home"):
        st.session_state["page"] = "home"
        st.rerun()


def handle_auth_callback() -> bool:
    """Returns True if an auth callback screen was rendered and app should stop."""
    action = st.query_params.get("auth_action", "")
    token_hash = st.query_params.get("token_hash", "")
    flow = st.query_params.get("flow", "")
    code = st.query_params.get("code", "")

    if flow:
        st.title("Complete social sign-in")
        try:
            details = auth_client().decode_oauth_flow(flow)
        except AuthError as exc:
            st.error(str(exc))
            if st.button("Return to sign in", key="invalid_flow_back"):
                _clean_auth_params()
                st.session_state["page"] = "auth"
                st.rerun()
            return True
        if st.query_params.get("error"):
            st.error("The provider did not authorize login. Return to the sign-in page and try again.")
        elif code:
            st.write(f"You returned from **{details['provider'].title()}**. Finish sign-in to access your workbench.")
            if st.button("Finish secure sign-in", type="primary"):
                try:
                    session = auth_client().finish_oauth(code, flow)
                    _clean_auth_params()
                    _enter_app(session)
                except AuthError as exc:
                    st.error(str(exc))
        else:
            st.warning("The provider did not return an authorization code. Try again.")
        if st.button("Return to sign in", key="oauth_back"):
            _clean_auth_params()
            st.session_state["page"] = "auth"
            st.rerun()
        return True

    if action in ("confirm", "reset"):
        st.title("Confirm your email" if action == "confirm" else "Reset your password")
        if not token_hash:
            st.error("The email link is missing its verification token. Request another email.")
        else:
            st.write("Click below to use your one-time email verification link.")
            if st.button("Confirm my email" if action == "confirm" else "Verify password-reset link", type="primary"):
                try:
                    response = auth_client().verify_email_token(token_hash, "email" if action == "confirm" else "recovery")
                    if action == "reset":
                        access = response.get("access_token")
                        if not access:
                            raise AuthError("Reset link was verified without a recovery session. Request a new reset email.")
                        st.session_state["reset_access_token"] = access
                        st.session_state["page"] = "reset"
                    else:
                        st.session_state["page"] = "auth"
                        st.session_state["auth_notice"] = True
                    _clean_auth_params()
                    st.rerun()
                except AuthError as exc:
                    st.error(str(exc))
        if st.button("Return to sign in", key="email_back"):
            _clean_auth_params()
            st.session_state["page"] = "auth"
            st.rerun()
        return True
    return False


def reset_page():
    st.title("Choose a new password")
    token = st.session_state.get("reset_access_token")
    if not token:
        st.error("No verified recovery session. Request a new password-reset email.")
        if st.button("Back to sign in"):
            st.session_state["page"] = "auth"
            st.rerun()
        return
    with st.form("update_password"):
        new_pw = st.text_input("New password", type="password")
        confirm_pw = st.text_input("Confirm new password", type="password")
        submit = st.form_submit_button("Update password", type="primary")
    if submit:
        if len(new_pw) < 10 or new_pw != confirm_pw:
            st.error("Passwords must match and contain at least 10 characters.")
        else:
            try:
                auth_client().update_password(token, new_pw)
                st.session_state.pop("reset_access_token", None)
                st.session_state["password_changed_notice"] = True
                st.session_state["page"] = "auth"
                st.rerun()
            except AuthError as exc:
                st.error(str(exc))


def profile_page():
    st.title("Complete your profile")
    st.write("For social sign-in, add your name and phone number once before using the workbench.")
    account = st.session_state.get("account")
    if not account:
        st.session_state["page"] = "auth"
        st.rerun()
    with st.form("oauth_profile"):
        name = st.text_input("Full name", value=account.get("name", ""))
        phone = st.text_input("Phone number", value=account.get("phone", ""))
        submitted = st.form_submit_button("Save profile and open studio", type="primary")
    if submitted:
        if not name.strip() or not PHONE_RE.fullmatch(phone.strip()):
            st.error("Enter your full name and valid phone number.")
        else:
            try:
                auth_client().update_profile(account["access_token"], name.strip(), phone.strip())
                account.update(name=name.strip(), phone=phone.strip())
                st.session_state["page"] = "studio"
                st.rerun()
            except AuthError as exc:
                st.error(str(exc))
    if st.button("Sign out", key="profile_logout"):
        clear_session()


def ensure_session() -> bool:
    account = st.session_state.get("account")
    if not account:
        return False
    try:
        st.session_state["account"] = auth_client().check_session(account)
        return True
    except (AuthError, KeyError) as exc:
        st.session_state.pop("account", None)
        st.session_state["page"] = "auth"
        st.error("Your login session has expired or is invalid. Please log in again.")
        return False
