# Seam Carving Lab — Email login + Private Dashboard (November 2026)

An OOAD-focused content-aware image resizing application (Python + NumPy + Pillow + Streamlit + Supabase).

**No Google or GitHub login buttons.** Authentication is email/password only. Existing Supabase email/password users continue to use their accounts.

## Run locally

1. Extract the ZIP and open `SeamCarvingLab_Complete` in VS Code.
2. In PowerShell:
   ```powershell
   py -m venv .venv
   .\.venv\Scripts\python.exe -m pip install -r requirements.txt
   .\.venv\Scripts\python.exe -m unittest discover -s tests -v
   .\.venv\Scripts\python.exe -m streamlit run app.py
   ```
3. In Streamlit Cloud secrets (or `.streamlit/secrets.toml` locally), supply Supabase settings as explained in `START_HERE.md`.

## Included features

- Public landing page with project details and developer contact information
- Supabase email/password signup, email confirmation, login, password reset, logout
- Dashboard showing account details, editable name/phone, current in-session image preview, and saved image history
- Save before/after images to a private Supabase bucket, inspect, download, delete
- Seam carving: backward and forward energy, vertical/horizontal reduction, basic seam insertion
- Energy map, seam overlay, optional rectangular protection mask
- Object removal without an arbitrary 350-seam cap, with a configurable *soft CPU time budget*
- Manual black/white mask PNG upload for protection or removal (no neural network needed)
- Optional pretrained SegFormer scene segmentation for category-based masks (requires extra packages and host memory)
- Multi-size ZIP output; uploads automatically downscaled when too large for responsive cloud processing
- unittest suite for algorithms, auth REST contract, mask helpers and storage requests

## Files

| Name | Purpose |
|---|---|
| `app.py` | Streamlit workbench and mask/removal workflows |
| `auth_ui.py` | Landing page, email signup/login, confirmation/reset forms and navigation |
| `auth_backend.py` | Email/password Supabase REST client (OAuth removed) |
| `dashboard_ui.py` | Dashboard, profile editor, saved before/after image previews |
| `image_history.py` | Private Supabase Storage/PostgREST operations using user JWT |
| `seamcarving/core.py` | Energy strategy, seam finding/removing, resizing engine |
| `seamcarving/advanced.py` | Object removal, SegFormer integration, multi-size output |
| `semantic_masks.py` | Manual PNG mask conversion with nearest-neighbor resampling |
| `supabase_history_setup.sql` | User-private database and storage access policies |
| `requirements-semantic.txt` | Optional pretrained-model packages for local machine |

## Limitations and academic accuracy

- The public app limits *working-image pixel count* through automatic downscaling. Pillow preprocessing is not seam carving.
- There is no fixed 350-seam cap on **object removal**, but a time budget and image geometry bound remain. Some outputs may be partial and are explicitly labelled.
- Object removal by seam carving can produce visible distortions; it does not reconstruct hidden background pixels.
- Pretrained SegFormer predicts ADE20K semantic categories; these are not equivalent to a learned attention-based saliency model.
- An uploaded binary mask is user-supplied and must not be described as an AI segmentation result.
- Multi-size ZIP files contain independently produced images, not a compact multi-size representation from the original 2007 paper.
- Dashboard only permanently retains files after the user explicitly clicks Save. The current image preview in the dashboard is temporary and cleared on logout.
- Real Supabase email delivery, RLS policies, deployment and SegFormer inference were **not** verified against the live service by local tests. Validate them after deployment.

See `START_HERE.md`, `EMAIL_SETUP.md` and `DASHBOARD_SETUP.md` for full instructions.
