# START HERE — Simplified Seam Carving Lab (no OAuth)

## 1. What changed from the old Enhanced ZIP?

- Removed Google and GitHub buttons from `auth_ui.py`.
- Removed OAuth client code and the `cryptography` dependency.
- Email/password login is retained with Supabase, including email confirmation and forgot password.
- Users go to **My dashboard** after logging in. Workbench remains one click away.
- Dashboard includes name/email/phone, edit-profile form, small preview of the currently opened image, and optionally saved original/output image pairs.
- Semantic protection control is disabled until a real mask is selected. Users can upload a white-on-black PNG mask even when SegFormer is unavailable.
- Object removal has **no arbitrary 350-seam operation limit**. It still has a 60-second default soft time budget and geometric limits for resource safety.

## 2. Local Windows instructions

1. Extract ZIP. Open `SeamCarvingLab_Complete` directory, the folder containing `app.py`.
2. Open VS Code terminal and run:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m streamlit run app.py
```

3. Browse to the local URL Streamlit prints (usually http://localhost:8501).
4. The landing page works without login. To use accounts, configure Supabase credentials.

## 3. Streamlit Cloud secrets

Open your Streamlit app → Manage app → Settings → Secrets. Preserve your real working Supabase values, in TOML format:

```toml
SUPABASE_URL = "https://YOUR_PROJECT_REF.supabase.co"
SUPABASE_ANON_KEY = "sb_publishable_YOUR_PUBLIC_KEY"
APP_URL = "https://YOUR_APP.streamlit.app"
SEAM_ENABLE_SEMANTIC = "0"
SEAM_OBJECT_TIME_BUDGET_SECONDS = "60"
```

- `APP_URL` must be your exact deployed HTTPS root URL without `#` or `?`.
- **Delete `AUTH_FLOW_SECRET`** from Secrets. It is no longer used, and you previously exposed one in chat.
- You do **not** need a Google or GitHub OAuth client, provider settings, or any client secrets.
- Do not put a Supabase `service_role` key in Streamlit Secrets.
- For email confirmation/reset links to work, configure the templates in `EMAIL_SETUP.md`.

## 4. Update the existing GitHub deployment

1. Extract this ZIP.
2. Copy **contents** of `SeamCarvingLab_Complete`, including `app.py`, `auth_ui.py`, `auth_backend.py`, `dashboard_ui.py`, `image_history.py`, `semantic_masks.py`, the `seamcarving` folder, and requirements files, into your **existing repository root**.
3. Keep your actual Secrets in the Streamlit dashboard; do not upload secrets.toml.
4. Commit and push to the same branch Streamlit deploys:

```bash
git add .
git commit -m "Simplify auth and add dashboard and mask workflows"
git push origin main
```

If Streamlit uses another branch, push that branch rather than `main`. Changes to `requirements.txt` cause automatic rebuild.

## 5. Dashboard: Supabase one-time setup

Go to `DASHBOARD_SETUP.md`. This is required to persist pictures across app restarts.

## 6. Manual mask — works WITHOUT an AI model

- Make a **black/white PNG** the same general shape as your photo: white = selected object/region, black = background.
- In Workbench, upload the photograph.
- Expand **Advanced workflows → Semantic masks — AI categories or uploaded PNG**.
- Upload the black/white PNG and click **Use uploaded mask for protection / object removal**.
- To protect it, enable **Protect selected semantic classes / uploaded mask** in sidebar, then run seam carving.
- To remove it, expand **Object removal — guided by mask**, change source to **Selected semantic classes / uploaded mask**, and click Remove marked object.
- Mask is resized by nearest-neighbor to the app's processed photo dimensions. This is a *manual mask*, NOT an AI-generated semantic prediction.

## 7. Optional AI segmentation

The basic `requirements.txt` intentionally skips large ML packages so the regular public site loads quickly.

For local AI support:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-semantic.txt
```

For Streamlit Community Cloud, add these **directly to the end of `requirements.txt`** (do not add `-r requirements-semantic.txt`, because that file already includes `-r requirements.txt`):

```text
torch>=2.2,<3
transformers>=4.40,<5
safetensors>=0.4
```

Set `SEAM_ENABLE_SEMANTIC = "1"` in Secrets. Reboot and click **Load semantic model and analyse image**. The model downloads `nvidia/segformer-b0-finetuned-ade-512-512` on first use. Shared hosting may run out of memory, in which case use the manual PNG mask or run on a more powerful host. Use Python 3.11 or 3.12 if available with compatible packages.

## 8. Object removal budget

No arbitrary 350 seam cap applies to object removal. The algorithm must still stop at geometric limits or the host's time budget. Optional control:

```toml
SEAM_OBJECT_TIME_BUDGET_SECONDS = "90"
```

This is a soft budget; cloud resource limits may still interrupt a large operation. Use small images for the OOAD demonstration.

## 9. Test it after deployment

1. Sign up using email and password, confirm the email, and log in.
2. See dashboard and verify name/email/phone.
3. Open Workbench, upload a photo; return to dashboard and see the temporary preview.
4. Process and save a result, return to dashboard and download it.
5. Use a second account to confirm users cannot see each other's history.
6. Test object removal (rectangle and manual mask), energy preview, backward/forward methods.
7. Test optional AI segmentation only if the model has been successfully installed.
