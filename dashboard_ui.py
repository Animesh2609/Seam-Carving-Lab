"""Streamlit dashboard for signed-in users with optional private image history."""
from __future__ import annotations
import streamlit as st
from auth_ui import nav, setting, auth_client, PHONE_RE
from image_history import HistoryConfig, HistoryError, ImageHistory


def history_client():
    return ImageHistory(HistoryConfig(setting('SUPABASE_URL'), setting('SUPABASE_ANON_KEY')))


def save_result_button(original, output, *, operation, filename, details, key):
    """Explicitly opt in to saving images; no uploaded pictures are stored silently."""
    from seamcarving import ImageExporter
    st.caption('Optional: save the processed input and output privately to your account.')
    if st.button('Save input & result to my dashboard', key=key):
        account = st.session_state.get('account')
        if not account:
            st.error('Please log in to save images.')
            return
        try:
            h, w = original.shape[:2]
            oh, ow = output.shape[:2]
            history_client().save(
                account, ImageExporter.png_bytes(original), ImageExporter.png_bytes(output),
                operation, filename, (w, h), (ow, oh), details)
            st.success('Saved to your private dashboard. Open Dashboard above to view it.')
        except HistoryError as exc:
            st.error(f'Image history is not configured: {exc}')


def dashboard_page():
    nav()
    account = st.session_state['account']
    st.title('My dashboard')
    st.caption('Account details, your currently opened image, and private saved results.')
    left, right = st.columns([1, 2], gap='large')
    with left:
        st.subheader('My account')
        st.write('**Name:**', account.get('name') or 'Not set')
        st.write('**Email:**', account.get('email') or 'Not set')
        st.write('**Phone:**', account.get('phone') or 'Not set')
        with st.expander('Edit my profile'):
            with st.form('dashboard_update_profile'):
                new_name = st.text_input('Full name', value=account.get('name') or '')
                new_phone = st.text_input('Phone number', value=account.get('phone') or '')
                save_profile = st.form_submit_button('Save profile')
            if save_profile:
                if not new_name.strip() or not PHONE_RE.fullmatch(new_phone.strip()):
                    st.error('Enter a name and valid phone number.')
                else:
                    try:
                        auth_client().update_profile(account['access_token'], new_name.strip(), new_phone.strip())
                        account['name'] = new_name.strip()
                        account['phone'] = new_phone.strip()
                        st.success('Profile updated.')
                        st.rerun()
                    except Exception as exc:
                        st.error(f'Could not update profile: {exc}')
        recent = st.session_state.get('recent_source')
        if recent:
            st.divider()
            st.subheader('This session')
            st.image(recent['preview_png'], caption=recent['name'], use_container_width=True)
            st.caption(f"Opened image: {recent['width']} × {recent['height']} px. "
                       'This preview is session-only and is not saved to the database.')
        if st.button('Return to image workbench', key='dashboard_to_studio', type='primary'):
            st.session_state['page'] = 'studio'
            st.rerun()
    with right:
        st.subheader('Private image history')
        st.caption('Only images you explicitly save are stored. Your files are kept in a private Supabase bucket.')
        try:
            records = history_client().list(account, limit=50)
        except HistoryError as exc:
            st.warning('Image history is not configured yet. See DASHBOARD_SETUP.md. ' + str(exc))
            return
        count = len(records)
        st.metric('Recent saved processing results', count)
        if count:
            a, b = st.columns(2)
            with a:
                st.metric('Seam-carving runs', sum(1 for r in records if r.get('operation') == 'Seam carving'))
            with b:
                st.metric('Object-removal runs', sum(1 for r in records if r.get('operation') == 'Object removal'))
        if not count:
            st.info('No saved images yet. Process an image, then click "Save input & result to my dashboard".')
            return
        chosen = st.selectbox('Choose a saved run',
            options=range(count),
            format_func=lambda index: (
                f"{records[index].get('created_at', '')[:16].replace('T', ' ')} · "
                f"{records[index].get('operation', '')} · "
                f"{records[index].get('source_name', '')}"))
        item = records[chosen]
        st.write(f"**Original:** {item['input_width']} × {item['input_height']} px  "
                 f"**Result:** {item['output_width']} × {item['output_height']} px")
        st.caption(f"Operation: {item['operation']} · Date: {item.get('created_at', '')}")
        try:
            input_bytes = history_client().download(account, item['input_path'])
            output_bytes = history_client().download(account, item['output_path'])
            a, b = st.columns(2)
            with a:
                st.image(input_bytes, caption='Saved input', use_container_width=True)
            with b:
                st.image(output_bytes, caption='Saved output', use_container_width=True)
                st.download_button('Download this output', data=output_bytes,
                                   file_name='saved_seam_result.png', mime='image/png')
        except HistoryError as exc:
            st.error('Could not load these images: ' + str(exc))
            return
        with st.expander('Delete this saved entry'):
            confirm = st.checkbox('I understand this permanently deletes the selected images')
            if st.button('Delete saved entry', disabled=not confirm, key='delete_history'):
                try:
                    history_client().delete(account, item)
                    st.success('Saved entry deleted.')
                    st.rerun()
                except HistoryError as exc:
                    st.error(str(exc))
