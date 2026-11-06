import streamlit as st
from auth_ui import (nav, landing, auth_page, reset_page, profile_page,
                     handle_auth_callback, ensure_session, setting)
st.set_page_config(page_title='Seam Carving Lab',page_icon='✂️',layout='wide')
st.markdown("""<style>
.block-container{max-width:1200px;padding-top:5.5rem;padding-bottom:3rem}
.hero{background:linear-gradient(125deg,#1c3046,#236478);color:white;border-radius:22px;padding:3.5rem 2.5rem;margin:1rem 0 2rem}
.hero h1{font-size:clamp(2.2rem,5vw,4rem);line-height:1.12;margin:.5rem 0}
.hero p{font-size:1.12rem;max-width:700px;color:#e0eaf0}
.eyebrow{letter-spacing:.15em;font-size:.8rem;color:#bce6e2}
</style>""",unsafe_allow_html=True)
# Email confirmation and password recovery use a one-time query token.
# Handle these BEFORE showing any normal page.
if handle_auth_callback():
    st.stop()

if 'page' not in st.session_state:
    st.session_state['page']='home'
if st.session_state['page']=='home':
    landing()
    st.stop()
if st.session_state['page']=='auth':
    auth_page()
    st.stop()
if st.session_state['page'] == 'reset':
    reset_page()
    st.stop()
if st.session_state['page'] == 'dashboard':
    if not ensure_session():
        st.stop()
    from dashboard_ui import dashboard_page
    dashboard_page()
    st.stop()
if st.session_state['page'] == 'profile':
    if not ensure_session():
        st.stop()
    profile_page()
    st.stop()
if not ensure_session():
    st.session_state['page'] = 'auth'
    st.stop()
# Clear password form fields after leaving the sign-in screen.
for _key in ('login_pw', 'signup_pw', 'signup_confirm'):
    st.session_state.pop(_key, None)
nav()
st.caption(f"Signed in as {st.session_state['account']['name']}")
st.title('Seam Carving Workbench')
st.caption('Content-aware resizing · object removal · masks · downloadable results')
from dashboard_ui import save_result_button
import io
import os
import numpy as np
import streamlit as st
from PIL import Image, ImageDraw
from seamcarving import (ResizeParameters, ImageDocument, SeamCarvingController,
                         ImageExporter, ImageResizer)


# Public hosting has shared CPU/RAM. Limit expensive operations per request.
MAX_PIXELS = int(os.getenv('SEAM_MAX_PIXELS', '360000'))
MAX_SEAM_OPERATIONS = int(os.getenv('SEAM_MAX_OPERATIONS', '350'))
# AI segmentation is optional; manual PNG masking works without Torch.
# Note: enabling this on small shared hosts may exceed available CPU/RAM.
import importlib.util
_semantic_allowed = str(setting('SEAM_ENABLE_SEMANTIC') or '0').strip().lower() not in ('0', 'false', 'no')
_semantic_installed = bool(importlib.util.find_spec('torch') and importlib.util.find_spec('transformers'))
ENABLE_SEMANTIC = _semantic_allowed and _semantic_installed
OBJECT_TIME_BUDGET = float(setting('SEAM_OBJECT_TIME_BUDGET_SECONDS') or 60)



controller = SeamCarvingController()

with st.sidebar:
    st.header('1 · Input')
    uploaded = st.file_uploader('Upload JPG or PNG', type=['jpg','jpeg','png'])
    st.info('Use 200–500 px images for responsive demonstrations. The algorithm processes seams individually.')

if uploaded is None:
    st.info('Upload an image to start. Then choose dimensions and inspect the energy map or seam overlay.')
    st.stop()

try:
    image = Image.open(uploaded).convert('RGB')
    original_dimensions = image.size
    if image.width * image.height > MAX_PIXELS:
        import math
        scale = math.sqrt(MAX_PIXELS / (image.width * image.height))
        image = image.resize((max(1, int(image.width * scale)), max(1, int(image.height * scale))), Image.Resampling.LANCZOS)
        st.info(f'Image downscaled from {original_dimensions[0]} × {original_dimensions[1]} to {image.width} × {image.height} for cloud processing.')
    original = np.asarray(image)
except Exception as exc:
    st.error(f'Unable to read the uploaded image: {exc}')
    st.stop()

h, w = original.shape[:2]
# Keep a small in-memory preview for the dashboard. Nothing is uploaded to
# Supabase until the user explicitly clicks a Save-to-dashboard button.
from hashlib import sha256
_fingerprint = sha256(uploaded.getvalue()).hexdigest()
if st.session_state.get('recent_source_id') != _fingerprint:
    _mini = image.copy()
    _mini.thumbnail((420, 280))
    _preview_buffer = io.BytesIO()
    _mini.save(_preview_buffer, format='PNG')
    st.session_state['recent_source_id'] = _fingerprint
    st.session_state['recent_source'] = {
        'name': uploaded.name, 'width': w, 'height': h,
        'preview_png': _preview_buffer.getvalue()}
document = ImageDocument(original)
with st.sidebar:
    st.header('2 · Resize settings')
    target_w = st.number_input('Target width (px)', min_value=1, max_value=2*w, value=max(1, round(w*0.8)))
    target_h = st.number_input('Target height (px)', min_value=1, max_value=2*h, value=max(1, round(h*0.8)))
    method = st.selectbox('Seam-selection method', ['Backward (gradient)', 'Forward (transition)'])
    st.header('3 · Protect region (optional)')
    protect = st.checkbox('Protect a rectangular area')
    if protect:
        st.caption('Coordinates refer to the ORIGINAL image. Protected pixels receive a large seam penalty.')
        x1 = st.number_input('Left X', 0, w-1, 0)
        x2 = st.number_input('Right X', 0, w, w)
        y1 = st.number_input('Top Y', 0, h-1, 0)
        y2 = st.number_input('Bottom Y', 0, h, h)
        if x1 >= x2 or y1 >= y2:
            st.error('Protection rectangle must have positive width and height.')
            st.stop()
        protection = np.zeros((h,w), dtype=bool)
        protection[y1:y2, x1:x2] = True
    else:
        protection = None

# Semantic classes selected in the advanced panel on a previous rerun can also
# be used as a protection mask for the main resizing workflow.
semantic_choice = st.session_state.get('semantic_selection')
valid_semantic_mask = bool(
    semantic_choice is not None
    and semantic_choice[0] == uploaded.getvalue()
    and np.asarray(semantic_choice[3], dtype=bool).any()
)
with st.sidebar:
    use_semantic_protection = st.checkbox(
        'Protect selected semantic classes / uploaded mask', value=False,
        disabled=not valid_semantic_mask,
        help='First select AI categories or upload a black-and-white mask in Advanced workflows.')
    if not valid_semantic_mask:
        st.caption('No mask selected yet. Go to Advanced workflows → Semantic masks below.')
if use_semantic_protection and valid_semantic_mask:
    semantic_protection = np.asarray(semantic_choice[3], dtype=bool)
    protection = semantic_protection.copy() if protection is None else (protection | semantic_protection)

c1, c2 = st.columns(2)
with c1:
    st.subheader('Original')
    st.image(image, use_container_width=True)
    st.caption(f'{w} × {h} pixels')
with c2:
    st.subheader('Energy map and first seam')
    try:
        energy, overlay = controller.preview(document, method, protection)
        energy_normalized = (255*(energy-energy.min())/(np.ptp(energy)+1e-9)).astype(np.uint8)
        tabs = st.tabs(['Energy map', 'Seam overlay'])
        with tabs[0]:
            st.image(energy_normalized, clamp=True, use_container_width=True)
        with tabs[1]:
            st.image(overlay, use_container_width=True)
    except Exception as exc:
        st.error(f'Preview failed: {exc}')

if protect and protection is not None:
    marked = image.copy()
    painter = ImageDraw.Draw(marked)
    painter.rectangle((x1,y1,x2-1,y2-1), outline=(255,0,0), width=3)
    st.caption('Protected rectangle (red outline; strong penalty, not an absolute guarantee)')
    st.image(marked, width=min(500,w))

st.divider()
if st.button('Run seam carving', type='primary'):
    if abs(int(target_w) - w) + abs(int(target_h) - h) > MAX_SEAM_OPERATIONS:
        st.error(f'For shared hosting, resize by at most {MAX_SEAM_OPERATIONS} total pixels '
                 'across width and height per operation. Try a smaller change.')
        st.stop()
    params = ResizeParameters(int(target_w), int(target_h), method)
    bar = st.progress(0.0)
    try:
        result = controller.resize(document, params, protection, progress=bar.progress)
        bar.progress(1.0)
        baseline = ImageResizer.conventional(original, params.width, params.height)
        st.session_state['result'] = (result, baseline, (w,h,params.width,params.height), method, (int(x1),int(x2),int(y1),int(y2)) if protect else None, uploaded.getvalue())
    except Exception as exc:
        st.error(f'Resizing failed: {exc}')

if 'result' in st.session_state:
    result, baseline, dims, previous_method, previous_mask, previous_file = st.session_state['result']
    if dims[:2] == (w,h) and dims[2:] == (int(target_w),int(target_h)) and previous_method == method and previous_mask == ((int(x1),int(x2),int(y1),int(y2)) if protect else None) and previous_file == uploaded.getvalue():
        st.subheader('Output comparison')
        a, b = st.columns(2)
        with a:
            st.markdown('**Pillow conventional resize (LANCZOS)**')
            st.image(baseline, use_container_width=True)
        with b:
            st.markdown('**Content-aware seam carving**')
            st.image(result.image, use_container_width=True)
        st.write(f'**Output:** {result.image.shape[1]} × {result.image.shape[0]} px  |  '
                 f'**Elapsed:** {result.seconds:.2f} s  |  '
                 f'**Removed:** {result.seams_removed} seams  |  '
                 f'**Inserted:** {result.seams_inserted} seams')
        st.download_button('Download seam-carved PNG', ImageExporter.png_bytes(result.image),
                           file_name='seam_carved.png', mime='image/png')
        st.download_button('Download conventional PNG', ImageExporter.png_bytes(baseline),
                           file_name='conventional_resize.png', mime='image/png')
        save_result_button(original, result.image, operation='Seam carving',
                           filename=uploaded.name, details={'method':method,
                           'width':int(target_w), 'height':int(target_h)},
                           key='save_resize_history')
    else:
        st.info('Settings have changed. Run seam carving again to generate an updated result.')

with st.expander('Algorithm and OOAD details'):
    st.markdown('''**Backward energy:** gradient magnitude and dynamic programming.  
**Forward energy:** transition costs estimate newly created edges (extension based on Rubinstein et al., 2008).  
**Protection:** a user-defined rectangle adds a large cost to pixels, discouraging their removal.  
**Enlargement:** repeated seam insertion (simple baseline, not optimized multi-seam insertion).  
**OOAD:** MVC-style separation, Strategy, service facade, encapsulated seam finder/editor, dataclasses and unit tests.  
**Limitations:** processing can be slow for large images; semantic segmentation is optional; object removal can distort backgrounds; multi-size export precomputes variants rather than a compact seam representation.''')

st.divider()
st.header('Advanced workflows')
st.caption('The following are extensions to the original OOAD proposal. Semantic segmentation is optional and uses a pretrained model.')
from seamcarving import ObjectRemovalService, SemanticSaliencyService, MultiSizeExporter

with st.expander('Semantic masks — AI categories or uploaded PNG', expanded=False):
    st.write('Create a mask from SegFormer (ADE20K) categories, or upload a black-and-white mask PNG. ' 
             'White indicates the region to protect/remove, black indicates the background. ' 
             'A manually uploaded mask is not AI segmentation.')
    from semantic_masks import mask_from_png
    custom_mask = st.file_uploader('Optional mask PNG (white = selected region)',
                                   type=['png'], key='manual_semantic_mask')
    if custom_mask is not None:
        try:
            user_mask = mask_from_png(custom_mask.getvalue(), (w, h))
            if user_mask.any():
                highlighted = original.copy()
                highlighted[user_mask] = (0.5*highlighted[user_mask] +
                    0.5*np.array([255, 60, 60])).astype(np.uint8)
                st.image(highlighted, caption=f'Manual mask: {int(user_mask.sum())} selected pixels',
                    width=min(650, w))
                if st.button('Use uploaded mask for protection / object removal', key='apply_manual_mask'):
                    st.session_state['semantic_selection'] = (
                        uploaded.getvalue(), ('Uploaded PNG mask',), 0.0, user_mask)
                    st.success('Mask selected. Return to the sidebar to protect it, or use it for object removal.')
                    st.rerun()
            else:
                st.warning('Uploaded mask is entirely black; no pixels are selected.')
        except Exception as exc:
            st.error(f'Cannot read mask PNG: {exc}')
    if not ENABLE_SEMANTIC:
        if not _semantic_installed:
            st.info('Optional AI model is not installed. The uploaded PNG mask above still works. '
                    'To enable AI, install requirements-semantic.txt and set SEAM_ENABLE_SEMANTIC=1.')
        else:
            st.info('AI semantic segmentation is disabled. Set SEAM_ENABLE_SEMANTIC=1 '
                    'in Secrets to enable the pretrained model.')
    if st.button('Load semantic model and analyse image', disabled=not ENABLE_SEMANTIC):
        try:
            @st.cache_resource(show_spinner='Loading SegFormer model (first run may download weights)...')
            def load_semantic():
                return SemanticSaliencyService()
            segmenter = load_semantic()
            with st.spinner('Running semantic segmentation...'):
                classes, confidence = segmenter.predict(original)
            st.session_state['semantic'] = (uploaded.getvalue(), classes, confidence, segmenter.labels)
        except Exception as exc:
            st.error(f'Semantic inference unavailable: {exc}')
            st.info('Install optional dependencies: pip install -r requirements-semantic.txt')

    semantic = st.session_state.get('semantic')
    if semantic and semantic[0] == uploaded.getvalue():
        _, classes, confidence, labels = semantic
        present = [(int(idx), labels.get(int(idx), str(idx))) for idx in np.unique(classes)]
        selected = st.multiselect('Select scene categories', options=[idx for idx, _ in present],
                                  format_func=lambda idx: f'{idx}: {labels.get(idx, idx)}')
        confidence_min = st.slider('Minimum model confidence', 0.0, 1.0, 0.35, 0.05)
        semantic_mask = SemanticSaliencyService.selected_mask(classes, confidence, selected, confidence_min)
        colored = original.copy()
        colored[semantic_mask] = (0.5 * colored[semantic_mask] + 0.5 * np.array([255, 80, 50])).astype(np.uint8)
        st.image(colored, caption=f'Selected semantic mask ({int(semantic_mask.sum())} pixels)', width=min(w, 650))
        # A category is not a usable selection until at least one pixel is marked.
        if selected and semantic_mask.any():
            st.session_state['semantic_selection'] = (uploaded.getvalue(), tuple(selected), confidence_min, semantic_mask)
        elif st.session_state.get('semantic_selection', (None,))[0] == uploaded.getvalue():
            existing = st.session_state['semantic_selection']
            # Do not overwrite a separately selected manual mask.
            if existing[1] != ('Uploaded PNG mask',):
                st.session_state.pop('semantic_selection', None)
    else:
        st.info('For AI-generated category masks, click the model button above. '
                'For a manual mask, upload a PNG and select Use uploaded mask.')

with st.expander('Object removal — guided by mask', expanded=False):
    st.write('Mark a rectangular object or use an AI/manual mask. The algorithm removes seams through that region. Restoration can add seams back; it does not generate missing background content.')
    source = st.radio('Removal mask source', ['Rectangle', 'Selected semantic classes / uploaded mask'], horizontal=True)
    if source == 'Rectangle':
        rx1, rx2 = st.slider('Object X range', 0, w, (max(0, w//3), max(1, 2*w//3)), key='remove_x')
        ry1, ry2 = st.slider('Object Y range', 0, h, (max(0, h//3), max(1, 2*h//3)), key='remove_y')
        remove_mask = np.zeros((h, w), dtype=bool)
        remove_mask[ry1:ry2, rx1:rx2] = True
    else:
        selected_data = st.session_state.get('semantic_selection')
        if selected_data and selected_data[0] == uploaded.getvalue():
            remove_mask = selected_data[3].copy()
        else:
            remove_mask = np.zeros((h, w), dtype=bool)
            st.warning('First select semantic classes or upload a mask PNG above.')
    mask_preview = original.copy()
    mask_preview[remove_mask] = (0.5*mask_preview[remove_mask] + 0.5*np.array([255, 30, 30])).astype(np.uint8)
    st.image(mask_preview, caption='Red overlay: pixels marked for removal', width=min(w, 650))
    restore = st.checkbox('Restore original dimensions after removal', value=True)
    st.caption('No fixed seam-count cap: the algorithm stops when the marked mask is cleared, '
               'the image reaches its geometric minimum, or the cloud processing time budget is reached.')
    st.caption(f'Cloud safety budget: {OBJECT_TIME_BUDGET:.0f} seconds per attempt; adjustable by the site owner.')
    if st.button('Remove marked object', type='primary'):
      if not remove_mask.any():
       st.error('Select a non-empty object region.')
      else:
        try:
          # Removal takes priority wherever masks overlap.
          effective_protection = None
          if protection is not None:
            effective_protection = (
              protection & ~remove_mask
                )
            with st.spinner('Removing marked object...'):
              obj_result = ObjectRemovalService(method).remove(
                original,
                remove_mask,
                effective_protection,
                restore_size=restore,
                max_seconds=OBJECT_TIME_BUDGET
              )
              st.session_state['object_result'] = (
                uploaded.getvalue(),
                obj_result
              )
        except Exception as exc:
          st.error(f'Object removal failed: {exc}')
    saved_obj = st.session_state.get('object_result')
    if saved_obj and saved_obj[0] == uploaded.getvalue():
        obj_result = saved_obj[1]
        st.image(obj_result.image, caption='Object-removal output', width=min(obj_result.image.shape[1], 650))
        st.write(f'Vertical seams removed: {obj_result.removed_vertical}; horizontal seams removed: {obj_result.removed_horizontal}; remaining marked pixels: {obj_result.remaining_mask_pixels}')
        if obj_result.timed_out:
            st.warning('Processing time budget reached. The result is partial; try a smaller '
                       'image or a more specific removal mask. The server remained protected.')
        if obj_result.remaining_mask_pixels:
            st.warning('The marked region was not fully removed; output is partial.')
        else:
            st.success('All marked pixels were eliminated from the tracked mask. Inspect visual artifacts.')
        st.download_button('Download object-removal PNG', ImageExporter.png_bytes(obj_result.image),
                           'object_removed.png', 'image/png')
        save_result_button(original, obj_result.image, operation='Object removal',
                           filename=uploaded.name, details={'method':method,
                           'removed_vertical':obj_result.removed_vertical,
                           'removed_horizontal':obj_result.removed_horizontal,
                           'remaining_mask_pixels':obj_result.remaining_mask_pixels},
                           key='save_object_history')

with st.expander('Multi-size image variants — ZIP export', expanded=False):
    st.write('Create several independently seam-carved sizes and package them with a manifest. This is not the compact multi-size seam representation from the 2007 paper.')
    presets = st.multiselect('Choose target widths as percentages of original', [50, 60, 70, 80, 90, 100], default=[60, 80, 100])
    keep_height = st.checkbox('Preserve original height for each variant', value=True)
    if st.button('Generate multi-size ZIP'):
        estimated_operations = sum(abs(w - max(1, round(w*p/100))) +
                                   (0 if keep_height else abs(h - max(1, round(h*p/100))))
                                   for p in presets)
        if estimated_operations > MAX_SEAM_OPERATIONS:
            st.error(f'These presets require about {estimated_operations} seam operations; '
                     f'the public demo limit is {MAX_SEAM_OPERATIONS}. Choose fewer/larger variants.')
        elif not presets:
            st.error('Select at least one size.')
        else:
            try:
                sizes = [(max(1, round(w*p/100)), h if keep_height else max(1, round(h*p/100))) for p in presets]
                progress_multi = st.progress(0.0)
                with st.spinner('Generating variants...'):
                    archive, manifest = MultiSizeExporter.build(original, sizes, method, protection, progress_multi.progress)
                st.session_state['multi_result'] = (uploaded.getvalue(), archive, manifest)
            except Exception as exc:
                st.error(f'Multi-size export failed: {exc}')
    saved_multi = st.session_state.get('multi_result')
    if saved_multi and saved_multi[0] == uploaded.getvalue():
        _, archive, manifest = saved_multi
        st.json(manifest)
        st.download_button('Download multi-size ZIP', archive, 'multi_size_variants.zip', 'application/zip')
        if st.button('Save all variants to my private dashboard', key='save_multi_history'):
            from dashboard_ui import history_client
            import zipfile as _zipfile
            successes = 0
            try:
                with _zipfile.ZipFile(io.BytesIO(archive)) as _z:
                    paths = [name for name in _z.namelist() if name.lower().endswith('.png')]
                    if not paths:
                        st.warning('No PNG variants in the generated ZIP.')
                    for image_name in paths:
                        payload = _z.read(image_name)
                        img = np.asarray(Image.open(io.BytesIO(payload)).convert('RGB'))
                        history_client().save(st.session_state['account'],
                            ImageExporter.png_bytes(original), payload,
                            'Multi-size variant', uploaded.name,
                            (w, h), (img.shape[1], img.shape[0]),
                            {'variant':image_name, 'method':method})
                        successes += 1
                if successes:
                    st.success(f'Saved {successes} variant(s) to your private dashboard.')
            except Exception as exc:
                st.error(f'Saved {successes} variants; remaining files could not be saved: {exc}')
