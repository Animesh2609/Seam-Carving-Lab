# Public deployment: Seam Carving Lab

## Recommended: Streamlit Community Cloud

1. Create a new GitHub repository and push the **contents of this folder** to its root. In particular, `app.py`, `requirements.txt`, and `.streamlit/config.toml` must be at repository root (the Streamlit config is relative to the working directory).
2. Visit https://share.streamlit.io/ and sign in with GitHub.
3. Select **Create app** → **Deploy a public app from GitHub** (wording may differ).
4. Choose your repository, the `main` branch, and entrypoint **`app.py`**.
5. Click Deploy. Wait for dependencies to install, then open the generated public `.streamlit.app` URL.
6. Share that URL. The local `localhost:8501` address is not public.

### Default public-hosting limits

The app uses 5 MB upload limit, maximum 360,000 image pixels and 350 seam operations per action by default. These are *application guardrails*, not guarantees of bounded runtime. Large object removal and multi-size exports can still be expensive. Environment variables allow adjustment:

- `SEAM_MAX_PIXELS=360000`
- `SEAM_MAX_OPERATIONS=350`
- `SEAM_ENABLE_SEMANTIC=0` (default)

**Semantic segmentation is disabled on the default public deployment** to avoid requiring large Torch/Transformers installations and model downloads on limited cloud resources. Core resizing, object removal and multi-size export remain available. To enable it on a capable host:

1. Install `requirements-semantic.txt` in addition to `requirements.txt` (for Community Cloud, add its packages to `requirements.txt`, or use a supported dependency mechanism).
2. Set `SEAM_ENABLE_SEMANTIC=1` in the host environment.
3. Ensure the server has enough memory, internet access to download the SegFormer model, and appropriate cache/storage. Model weights are downloaded on first use.

### Security and availability notes

- This is a **public, unauthenticated demo**. Do not upload private or sensitive images. The host processes uploaded images and Streamlit session state may retain results while sessions are active.
- The app does not intentionally save uploaded images to a persistent database. Hosting-provider logs, platform retention, and caching policies are separate considerations.
- Shared CPU/RAM resources and cold starts can affect response times. Free hosting may sleep when idle and does not guarantee continuous uptime.
- For more control, use a paid VM/container with more memory, authentication and request limits.
- The algorithm remains CPU-heavy because it processes seams iteratively. Test with small images.

## Run locally

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Localhost is for development. For the public version, use the deployed `.streamlit.app` link.

## Attribution

App author: Animesh Singh (2026H1120144P). Research foundation: Avidan & Shamir (2007), *Seam Carving for Content-Aware Image Resizing*. Forward-energy extension: Rubinstein, Shamir & Avidan (2008). Preserve research references in the academic report and README.
