# Seam Carving Lab — November 2026 upgrade

This project is based on your **SeamCarvingLab_Full_Auth_OAuth_Recovery** source, and preserves its original core processing, registration and OAuth functions while adding private history and improving advanced workflows.

## What changed

| Requirement | Implementation |
| --- | --- |
| Google and GitHub login | Uses the project's existing Supabase OAuth/PKCE implementation in `auth_backend.py` and `auth_ui.py`; buttons work **after** provider and secret setup below |
| Semantic segmentation | `SemanticSaliencyService` uses SegFormer (ADE20K); installed via `requirements.txt` and enabled by default when dependencies are available, unless `SEAM_ENABLE_SEMANTIC = "0"` |
| Semantic protection mask | Select detected class labels in Advanced workflows, then enable **Protect selected semantic classes** in the sidebar, and run resizing |
| Semantic object mask | In Object removal, choose **Selected semantic classes** as the mask source after analysing the uploaded image |
| Object removal | Removed the arbitrary 350-seam validation and number field. The algorithm runs until the mask is cleared or geometric/time limits are reached; partial outputs are reported honestly |
| Dashboard | New authenticated dashboard showing name, email, phone and explicitly saved before/after images using Supabase Storage and row-level security |

## Required Streamlit Cloud Secrets

In Streamlit Community Cloud → App → Settings → Secrets, keep the following in **TOML** format:

```toml
SUPABASE_URL = "https://YOUR_PROJECT_REF.supabase.co"
SUPABASE_ANON_KEY = "sb_publishable_YOUR_PUBLIC_KEY"
APP_URL = "https://YOUR_REAL_APP.streamlit.app"
AUTH_FLOW_SECRET = "YOUR_RANDOM_FERNET_KEY"
SEAM_ENABLE_SEMANTIC = "1"
SEAM_OBJECT_TIME_BUDGET_SECONDS = "60"
```

Do **not** paste secrets into GitHub. Do **not** use `service_role` or `sb_secret_...` in the Streamlit app.

Generate `AUTH_FLOW_SECRET` locally using:

```powershell
python -m pip install cryptography
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

`APP_URL` must be the real HTTPS Streamlit address **without** a hash fragment (`#...`), query string or trailing slash.

## Google sign-in setup

1. Supabase dashboard → Authentication → Sign In / Providers → Google → Enable.
2. Google Cloud Console → **Google Auth Platform**: create a project, configure the OAuth consent screen (testing or production), and create a **Web application OAuth client**.
3. Enter the origin of your deployed Streamlit site in Authorized JavaScript origins, e.g. `https://YOUR_APP.streamlit.app`.
4. Enter Supabase's exact callback URL in Authorized redirect URIs: `https://YOUR_PROJECT_REF.supabase.co/auth/v1/callback`.
5. Copy **Google Client ID and Client Secret into Supabase's Google provider page** (not Streamlit Secrets).
6. While the Google OAuth consent screen is in **Testing**, add the Google accounts you plan to test; publish the OAuth app when ready for visitors.

## GitHub sign-in setup

1. GitHub → Settings → Developer Settings → OAuth Apps → New OAuth App.
2. Application name: `Seam Carving Lab`.
3. Homepage URL: `https://YOUR_APP.streamlit.app`.
4. Authorization callback URL: `https://YOUR_PROJECT_REF.supabase.co/auth/v1/callback`.
5. Copy the **GitHub OAuth Client ID and Client Secret into Supabase** → Authentication → Sign In / Providers → GitHub → Enable → Save.

## Supabase URL Configuration

Supabase → Authentication → URL Configuration:

- **Site URL**: `https://YOUR_APP.streamlit.app`
- **Redirect URLs**: add your exact Streamlit URL and, for the encrypted flow query, `https://YOUR_APP.streamlit.app/**` (Supabase glob patterns as supported by the dashboard). If necessary, also allow `https://YOUR_APP.streamlit.app?**` when query redirects are blocked. Inspect your own OAuth callback URL under auth settings to verify the allowlist.

The Google/GitHub identity-provider redirect URL is **Supabase's** `/auth/v1/callback`, not the Streamlit URL. Supabase then redirects users back to the app; the app finishes PKCE on the returned `?flow=...&code=...` link.

The existing flow opens a new tab and may require the user to click **Finish secure sign-in** after authorization.

## Enable semantic AI on Streamlit Cloud

1. Publish this project's `requirements.txt` (it contains `torch`, `transformers`, and `safetensors`).
2. In Streamlit Cloud → App settings → General, choose **Python 3.11 or 3.12**, if available, for smoother ML dependency compatibility, then reboot.
3. Keep `SEAM_ENABLE_SEMANTIC = "1"` in Secrets (optional; auto-enabled when dependencies exist).
4. Upload a modest photo (the public app downsizes to the configured pixel budget).
5. Expand **Advanced workflows → Semantic saliency → Load semantic model and analyse image**. First run downloads the ADE20K SegFormer weights.
6. Choose classes, e.g. `person`, `building`, `sky` if recognized. The app previews the class mask.
7. Enable the sidebar semantic protection checkbox and **Run seam carving**; or choose semantic classes as the object removal mask.

**Important**: A hosted Streamlit instance can run out of RAM, crash during model installation/inference or cold-start when using PyTorch. The update reduces inference memory by resizing *two 2D maps* instead of all 150 ADE20K channels, but real cloud inference is **not guaranteed**. If the deployment runs out of memory, run semantic analysis locally or use a larger inference host. The model predicts semantic classes; this is not the same as a human-attention saliency metric.

## Object removal without a hard seam cap

The previous application blocked more than 350 seam operations. This arbitrary object-removal limit and number input have been removed. The operation now stops when:

1. Every marked removal pixel has been removed;
2. The remaining image cannot be shrunk further (1×1 geometric limit); or
3. The soft time budget, set by `SEAM_OBJECT_TIME_BUDGET_SECONDS`, has been reached between removal seams. Restoring size afterward can take additional time.

A **partial result** is displayed and labelled if the removal mask remains. The optional restore-size operation can be expensive for very large removals, so prefer small images and uncheck restoration while diagnosing performance. No public server can promise unbounded CPU/RAM work for arbitrary uploads.

## Dashboard

Follow `DASHBOARD_SETUP.md`, create the private Storage bucket and execute `supabase_history_setup.sql` in Supabase's SQL editor. After that, each user can save/review their own resized, object-removed and multi-size output variants. No images are stored without the user's click.

## Run/tests locally

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m streamlit run app.py
```

You can also install only non-ML dependencies locally to run the core tests by installing NumPy, Pillow, requests and cryptography.

## Honest validation status

The ZIP was syntax-checked and unit-tested in the sandbox. It has **not** been connected to your live Supabase project, Google/GitHub credentials, or full pretrained model weights, so live authentication, Storage permissions and model inference must still be tested after deployment. This is an OOAD educational demonstration, not a production-audited service.
