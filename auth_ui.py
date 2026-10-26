"""Landing page and Supabase email/password authentication."""
import os
import re
import requests
import streamlit as st


def setting(name):
    if os.getenv(name):
        return os.environ[name]
    try:
        return st.secrets.get(name, '')
    except (FileNotFoundError, KeyError):
        return ''


def configured():
    return bool(setting('SUPABASE_URL') and setting('SUPABASE_ANON_KEY'))


def auth_request(endpoint, payload):
    url = setting('SUPABASE_URL').rstrip('/')
    key = setting('SUPABASE_ANON_KEY')
    if not url or not key:
        raise ValueError('Account service is not configured.')
    try:
        response = requests.post(f'{url}/auth/v1/{endpoint}', json=payload,
            headers={'apikey': key, 'Content-Type': 'application/json'}, timeout=20)
        data = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise ValueError('Unable to contact the authentication service.') from exc
    if response.status_code >= 400:
        raise ValueError(data.get('msg') or data.get('error_description') or data.get('message') or 'Authentication failed.')
    return data


def nav():
    a, b = st.columns([4, 1])
    with a:
        st.markdown('### ✂️ Seam Carving Lab')
    with b:
        if st.session_state.get('account'):
            if st.button('Sign out', use_container_width=True):
                for key in ('account','result','object_result','multi_result','semantic','semantic_selection'):
                    st.session_state.pop(key,None)
                st.session_state['page']='home'
                st.rerun()
        elif st.session_state.get('page')=='home':
            if st.button('Sign in',type='primary',use_container_width=True):
                st.session_state['page']='auth'
                st.rerun()


def landing():
    nav()
    st.markdown("""<section class="hero"><div class="eyebrow">CONTENT-AWARE IMAGE EDITING</div>
      <h1>Resize smarter.<br>Preserve what matters.</h1>
      <p>Seam carving, object removal, energy maps, semantic masks and multi-size image export in one interactive workbench.</p>
      </section>""",unsafe_allow_html=True)
    c1,c2,c3=st.columns(3)
    with c1:
        st.subheader('🖼️ Smart resizing')
        st.write('Remove or insert low-energy seams while comparing results with conventional resizing.')
    with c2:
        st.subheader('🧩 Object removal')
        st.write('Mark unwanted regions and guide the algorithm through them.')
    with c3:
        st.subheader('🔎 Explore the algorithm')
        st.write('Inspect energy maps, seam overlays and multiple output sizes.')
    st.divider()
    st.subheader('How it works')
    st.write('**Create an account → Upload an image → Select a method → Compare and download.**')
    if st.button('Get started',type='primary'):
        st.session_state['page']='auth'
        st.rerun()
    st.divider()
    st.subheader('About the team')
    st.markdown('**Animesh Singh (2026H1120144P)** — Developer and project author')
    st.markdown('**Email:** [animeshsingh1403@gmail.com](mailto:animeshsingh1403@gmail.com)')
    st.markdown('**Mobile:** [7607141408](tel:7607141408)')
    st.caption('Research basis: Avidan & Shamir, Seam Carving for Content-Aware Image Resizing (2007).')


def auth_page():
    nav()
    st.title('Welcome to Seam Carving Lab')
    st.write('Create your account or log in to access the image-processing studio.')
    if not configured():
        st.warning('The site owner must configure Supabase before sign-up or login can work.')
    create,login=st.tabs(['New member · Sign up','Existing member · Log in'])
    with create:
        with st.form('signup'):
            name=st.text_input('Full name')
            phone=st.text_input('Phone number')
            email=st.text_input('Email address')
            password=st.text_input('Choose a password',type='password')
            confirm=st.text_input('Confirm password',type='password')
            submit=st.form_submit_button('Create account',type='primary',disabled=not configured())
        if submit:
            if not name.strip() or not re.fullmatch(r'[+0-9() -]{7,20}',phone.strip()):
                st.error('Enter your name and a valid phone number.')
            elif not re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+',email.strip()):
                st.error('Enter a valid email address.')
            elif len(password)<10:
                st.error('Use at least 10 characters for your password.')
            elif password!=confirm:
                st.error('Passwords do not match.')
            else:
                try:
                    auth_request('signup',{'email':email.strip().lower(),'password':password,
                        'data':{'full_name':name.strip(),'phone':phone.strip()}})
                    st.success('Registration submitted. Check your inbox for an email confirmation link.')
                    st.info('Your email is your login username. Passwords are never emailed.')
                except ValueError as exc:
                    st.error(str(exc))
    with login:
        with st.form('login'):
            login_email=st.text_input('Username (email address)')
            login_password=st.text_input('Password',type='password')
            go=st.form_submit_button('Log in',type='primary',disabled=not configured())
        if go:
            try:
                data=auth_request('token?grant_type=password',{'email':login_email.strip().lower(),'password':login_password})
                user=data.get('user') or {}
                st.session_state['account']={'id':user.get('id'),'email':user.get('email'),
                    'name':(user.get('user_metadata') or {}).get('full_name') or login_email}
                st.session_state['page']='studio'
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))
        with st.expander('Forgot password?'):
            reset=st.text_input('Email for password reset')
            if st.button('Send reset email',disabled=not configured()):
                try:
                    auth_request('recover',{'email':reset.strip().lower()})
                    st.success('If an account exists, a password-reset email will be sent.')
                except ValueError as exc:
                    st.error(str(exc))
    st.divider()
    st.subheader('Other sign-in options')
    st.info('Google and GitHub OAuth require a separate provider and callback integration; they are not active in this build. Streamlit accounts cannot be used as a general third-party login provider.')
    if st.button('← Back to home'):
        st.session_state['page']='home'
        st.rerun()
