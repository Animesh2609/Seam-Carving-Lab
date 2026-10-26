"""Streamlit View: all image-processing logic is delegated to the controller."""
import io
import os
import math
import numpy as np
import streamlit as st
from PIL import Image, ImageDraw

from seamcarving import (
    ResizeParameters,
    ImageDocument,
    SeamCarvingController,
    ImageExporter,
    ImageResizer
)

def prepare_image(image, max_pixels=360_000):
    width, height = image.size
    total_pixels = width * height

    if total_pixels > max_pixels:
        scale = math.sqrt(max_pixels / total_pixels)

        new_width = max(1, int(width * scale))
        new_height = max(1, int(height * scale))

        image = image.resize(
            (new_width, new_height),
            Image.Resampling.LANCZOS
        )

    return image

st.set_page_config(page_title='Seam Carving Lab', page_icon='🖼️', layout='wide')
# Public hosting has shared CPU/RAM. Limit expensive operations per request.
MAX_PIXELS = int(os.getenv('SEAM_MAX_PIXELS', '360000'))
MAX_SEAM_OPERATIONS = int(os.getenv('SEAM_MAX_OPERATIONS', '350'))
ENABLE_SEMANTIC = os.getenv('SEAM_ENABLE_SEMANTIC', '0') == '1'

st.title('Seam Carving Lab')
st.caption('An OOAD workbench for content-aware image resizing · Animesh Singh (2026H1120144P)')
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

    original_width, original_height = image.size

    # Automatically resize oversized uploads
    image = prepare_image(image, MAX_PIXELS)

    # Convert the processed image to a NumPy array
    original = np.asarray(image)

except Exception as exc:
    st.error(f'Unable to read the uploaded image: {exc}')
    st.stop()

h, w = original.shape[:2]

# Inform the user if automatic downscaling occurred
if (w, h) != (original_width, original_height):
    st.info(
        f"Your uploaded image was {original_width} × {original_height} pixels. "
        f"It has been automatically resized to {w} × {h} pixels "
        "for faster processing on the public server."
    )

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
with st.sidebar:
    use_semantic_protection = st.checkbox('Protect selected semantic classes', value=False,
        help='Analyse the image and select semantic classes in Advanced workflows first.')
if use_semantic_protection:
    if semantic_choice is None or semantic_choice[0] != uploaded.getvalue():
        st.sidebar.warning('No semantic mask for this image. Analyse and select classes below.')
    else:
        semantic_protection = semantic_choice[3]
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

with st.expander('Semantic saliency — pretrained scene segmentation', expanded=False):
    st.write('Detect scene categories with SegFormer (ADE20K), then select classes to protect or remove. Model weights download on first use; no semantic results are invented when the model is unavailable.')
    if not ENABLE_SEMANTIC:
        st.info('Semantic segmentation is disabled on this deployment to conserve memory. '
                'The feature can be enabled by the host after installing optional dependencies '
                'and setting SEAM_ENABLE_SEMANTIC=1.')
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
        st.session_state['semantic_selection'] = (uploaded.getvalue(), tuple(selected), confidence_min, semantic_mask)
    else:
        st.info('Click the button above to run the optional semantic model.')

with st.expander('Object removal — guided by mask', expanded=False):
    st.write('Choose an object region. Seams are attracted to marked pixels until the marked region disappears or the image reaches its size limit. Optional restoration inserts seams to recover the original dimensions.')
    source = st.radio('Removal mask source', ['Rectangle', 'Selected semantic classes'], horizontal=True)
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
            st.warning('First analyse the image and select semantic classes above.')
    mask_preview = original.copy()
    mask_preview[remove_mask] = (0.5*mask_preview[remove_mask] + 0.5*np.array([255, 30, 30])).astype(np.uint8)
    st.image(mask_preview, caption='Red overlay: pixels marked for removal', width=min(w, 650))
    restore = st.checkbox('Restore original dimensions after removal', value=True)
    max_remove = st.number_input('Maximum seams for object removal', min_value=1, max_value=max(1, w+h), value=max(1, w+h-2))
    if st.button('Remove marked object', type='primary'):
        if int(max_remove) > MAX_SEAM_OPERATIONS:
            st.error(f'Choose at most {MAX_SEAM_OPERATIONS} maximum seams for this deployment.')
        elif not remove_mask.any():
            st.error('Select a non-empty object region.')
        elif protection is not None and np.any(remove_mask & protection):
            st.error('Removal mask overlaps the protection rectangle. Adjust the regions.')
        else:
            try:
                with st.spinner('Removing marked object...'):
                    obj_result = ObjectRemovalService(method).remove(
                        original, remove_mask, protection, restore_size=restore,
                        max_seams=int(max_remove))
                st.session_state['object_result'] = (uploaded.getvalue(), obj_result)
            except Exception as exc:
                st.error(f'Object removal failed: {exc}')
    saved_obj = st.session_state.get('object_result')
    if saved_obj and saved_obj[0] == uploaded.getvalue():
        obj_result = saved_obj[1]
        st.image(obj_result.image, caption='Object-removal output', width=min(obj_result.image.shape[1], 650))
        st.write(f'Vertical seams removed: {obj_result.removed_vertical}; horizontal seams removed: {obj_result.removed_horizontal}; remaining marked pixels: {obj_result.remaining_mask_pixels}')
        if obj_result.remaining_mask_pixels:
            st.warning('The marked region was not fully removed; output is partial.')
        else:
            st.success('All marked pixels were eliminated from the tracked mask. Inspect visual artifacts.')
        st.download_button('Download object-removal PNG', ImageExporter.png_bytes(obj_result.image),
                           'object_removed.png', 'image/png')

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
