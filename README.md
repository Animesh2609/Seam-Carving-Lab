# Seam Carving Lab — OOAD implementation

Research foundation: Shai Avidan and Ariel Shamir, **Seam Carving for Content-Aware Image Resizing**, ACM Transactions on Graphics 26(3), 2007, Article 10, https://doi.org/10.1145/1276377.1276390.

Forward-energy extension: Michael Rubinstein, Ariel Shamir, Shai Avidan, **Improved Seam Carving for Video Retargeting**, ACM Transactions on Graphics 27(3), 2008.

## Install on Windows

Requires Python 3.10 or newer. From this folder:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
streamlit run app.py
```

If PowerShell blocks activation, use `.venv\Scripts\python.exe -m pip install -r requirements.txt` and `.venv\Scripts\python.exe -m streamlit run app.py`.

## File structure

- `app.py` — Streamlit View; upload, previews, mask controls, metrics, download.
- `seamcarving/core.py` — Model and services, independent of Streamlit.
- `seamcarving/__init__.py` — public class exports.
- `tests/test_core.py` — unit/integration tests.
- `requirements.txt` — dependencies.

## Features and traceability

| Feature | Implemented by |
|---|---|
| JPEG/PNG upload, RGB decoding | Pillow in `app.py` |
| Gradient energy | `BackwardEnergy.energy` |
| Dynamic programming/backtracking | `SeamFinder.backward` |
| Forward-energy transition costs | `ForwardEnergy.find_seam` |
| Vertical seam remove/insert | `SeamEditor` |
| Horizontal resizing | transposition in `SeamCarvingService` |
| Energy map and seam overlay | `SeamCarvingController.preview` |
| Protected rectangle | boolean mask with seam penalty, updated during resize |
| Standard resizing comparison | `ImageResizer` using Pillow LANCZOS |
| Runtime and seam counts | `ProcessingResult` |
| PNG export | `ImageExporter` |
| OOAD patterns | Strategy, MVC-style separation, Facade/service, GRASP principles |

## Design notes

- `ImageDocument` owns original/result arrays. Original is never modified.
- `ResizeParameters` stores target dimensions and chosen energy strategy.
- `SeamCarvingController` receives UI requests and selects an energy strategy.
- `EnergyStrategy` is an abstract class; `BackwardEnergy` and `ForwardEnergy` are concrete strategies.
- `SeamFinder` uses dynamic programming and backtracking.
- `SeamEditor` owns seam insertion/removal/overlay.
- `SeamCarvingService` is a facade coordinating seam operations.
- `ImageExporter` saves PNG; `ImageResizer` provides a conventional comparison.

## Limitations (important for report/viva)

1. This is a **working educational implementation**, not a complete reproduction of the 2007 paper. It does not implement semantic saliency, general object removal, or multi-size representations.
2. The forward-energy implementation uses RGB L1 transition costs; its displayed energy map is the **backward gradient map** for illustration, not a forward-energy cost map.
3. Enlargement uses greedy repeated seam insertion, not the paper's optimized multi-seam insertion ordering. Results may show repeated artifacts.
4. Protected regions receive a **high penalty**, not an absolute constraint. If every possible seam crosses the protected region, some protected pixels can still be removed.
5. Python loops make large reductions slow. For demos start with ~200–500 px images and small changes.
6. Width is adjusted before height, so results depend on operation order. The algorithm does not globally optimize across both directions.
7. If Streamlit settings change after a run, rerun to update output. Protection rectangle changes should also be followed by a rerun.

## Suggested demo

1. Upload a landscape photograph around 400x300.
2. Preview gradient energy and the first seam overlay.
3. Reduce width to 350, height to 280 using backward energy.
4. Compare against Pillow conventional resize; download result.
5. Change to forward energy and rerun.
6. Enable a protection rectangle around a prominent subject and compare.
7. Demonstrate modest enlargement (e.g. 420x300), and explain the limitations.
8. Run `python -m unittest discover -s tests -v` and capture the results for your report.

## Advanced workflows (upgraded version)

### Object removal
In **Advanced workflows → Object removal**, select a rectangular region or use a semantic class mask. The algorithm applies a strong negative penalty to pixels marked for removal and repeatedly removes seams. If enabled, it inserts seams afterward to restore the input dimensions. This is guided content-aware removal, not generative inpainting; complex shapes and large objects can distort.

### Semantic saliency / scene segmentation (optional)
Install the additional packages:

```powershell
pip install -r requirements-semantic.txt
```

Open **Advanced workflows → Semantic saliency**, click **Load semantic model and analyse image**, then select detected scene categories. The model is `nvidia/segformer-b0-finetuned-ade-512-512` (ADE20K labels). It downloads pretrained weights the first time, requires internet for that download, and may consume substantial RAM. Results are semantic segmentation classes, not a human-attention saliency model; the chosen classes serve as a *semantic importance mask*. Low-confidence predictions can be excluded with the confidence slider. These masks can be used for object removal, or use the existing protection rectangle for resizing.

### Multi-size variants
Open **Advanced workflows → Multi-size image variants**, choose size percentages and download a ZIP of resized PNGs and a `manifest.json`. These are *independently precomputed sizes*, **not** the original paper's efficient multi-size seam-order data structure.

### Algorithmic scope and caveats
- The 2007 paper motivates seam carving, seam insertion, object removal, and multi-size images. Forward-energy seam selection is associated with Rubinstein et al. (2008).
- Semantic segmentation is a modern optional extension, not part of the original 2007 implementation.
- Semantic segmentation and object removal are not guaranteed to preserve every important object; inspect outputs and compare against conventional resizing.
- For smooth performance start with 100–300 pixel demo images. Large object masks can require many sequential seam operations.
- Do not claim the code reconstructs hidden content, provides pixel-perfect object removal, or implements the original compact multi-size image representation.

To apply selected semantic classes to **normal resizing**, after selecting the classes, enable **Protect selected semantic classes** in the sidebar and run seam carving again. The semantic mask and manually selected protection rectangle are combined.


## Public hosting

See [DEPLOYMENT.md](DEPLOYMENT.md) for step-by-step instructions for Streamlit Community Cloud, limits and optional semantic dependencies.
