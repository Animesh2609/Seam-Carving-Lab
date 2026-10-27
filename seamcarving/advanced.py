"""Optional advanced workflows: object removal, semantic segmentation and size presets.

Semantic segmentation requires optional Torch/Transformers weights; no heuristic is
misrepresented as semantic inference. Multi-size export stores independently
computed variants, not the compact seam tree of Avidan & Shamir (2007).
"""
from __future__ import annotations
from dataclasses import dataclass
import io
import json
import zipfile
import numpy as np
from PIL import Image
from .core import (BackwardEnergy, ForwardEnergy, SeamEditor, SeamCarvingService,
                   ResizeParameters, ImageExporter)


@dataclass
class ObjectRemovalResult:
    image: np.ndarray
    removed_vertical: int
    removed_horizontal: int
    remaining_mask_pixels: int
    restored_size: bool


class ObjectRemovalService:
    """Remove a marked object by steering seams through a removal mask.

    Optionally restores dimensions by inserting new seams. This is an
    approximation: restored pixels are synthesized from neighbours, not
    reconstruction of hidden scene content.
    """
    def __init__(self, method='Backward (gradient)', removal_strength=1e7,
                 protection_strength=1e7):
        strategies = {'Backward (gradient)': BackwardEnergy,
                      'Forward (transition)': ForwardEnergy}
        if method not in strategies:
            raise ValueError('Unknown energy method')
        self.strategy = strategies[method]()
        self.removal_strength = float(removal_strength)
        self.protection_strength = float(protection_strength)

    def remove(self, image, removal_mask, protection_mask=None, restore_size=True,
               max_seams=None, progress=None):
        image = np.asarray(image)
        if image.ndim != 3 or image.shape[2] != 3 or image.dtype != np.uint8:
            raise ValueError('Expected RGB uint8 image')
        h0, w0 = image.shape[:2]
        removal = np.asarray(removal_mask, dtype=bool).copy()
        if removal.shape != (h0, w0) or not removal.any():
            raise ValueError('Select a non-empty removal region matching the image')
        protect = (np.asarray(protection_mask, dtype=bool).copy()
                   if protection_mask is not None else np.zeros((h0, w0), dtype=bool))
        if protect.shape != (h0, w0):
            raise ValueError('Protection mask must match image dimensions')
        if np.any(removal & protect):
            raise ValueError('Removal and protection masks must not overlap')
        output = image.copy()
        vertical = horizontal = 0
        limit = int(max_seams) if max_seams is not None else w0 + h0 - 2
        if limit < 1:
            raise ValueError('max_seams must be positive')

        for step in range(limit):
            if not removal.any():
                break
            ys, xs = np.nonzero(removal)
            box_width = int(xs.max() - xs.min() + 1)
            box_height = int(ys.max() - ys.min() + 1)
            # Prefer the direction that needs fewer seams to cross the object.
            # If one dimension reaches 1, use the other direction.
            use_horizontal = (box_height < box_width and output.shape[0] > 1)
            if output.shape[1] <= 1:
                use_horizontal = True
            if output.shape[0] <= 1:
                use_horizontal = False
            if output.shape[0] <= 1 and output.shape[1] <= 1:
                break
            if use_horizontal:
                work = np.transpose(output, (1, 0, 2))
                rmask, pmask = removal.T, protect.T
            else:
                work, rmask, pmask = output, removal, protect
            penalty = self.protection_strength * pmask.astype(float) - self.removal_strength * rmask.astype(float)
            seam = self.strategy.find_seam(work, penalty)
            work = SeamEditor.remove(work, seam)
            rmask = SeamEditor.remove(rmask, seam)
            pmask = SeamEditor.remove(pmask, seam)
            if use_horizontal:
                output, removal, protect = np.transpose(work, (1, 0, 2)), rmask.T, pmask.T
                horizontal += 1
            else:
                output, removal, protect = work, rmask, pmask
                vertical += 1
            if progress:
                progress(min((step + 1) / limit, 1.0))

        remaining = int(removal.sum())
        if remaining:
            # Do not claim success when the marked region is still present.
            return ObjectRemovalResult(output, vertical, horizontal, remaining, False)

        if restore_size and (vertical or horizontal):
            # Simple repeated insertion; retains original size but can create artifacts.
            service = SeamCarvingService(self.strategy)
            params = ResizeParameters(w0, h0)
            output = service.resize(output, params).image
        return ObjectRemovalResult(output, vertical, horizontal, remaining, bool(restore_size))


class SemanticSaliencyService:
    """ADE20K semantic segmentation using optional SegFormer model.

    Downloads weights on first use unless already cached. Returns per-pixel
    class IDs, and maps the chosen class to a saliency/protection mask.
    """
    MODEL_ID = 'nvidia/segformer-b0-finetuned-ade-512-512'

    def __init__(self, model_id=None):
        self.model_id = model_id or self.MODEL_ID
        try:
            import torch
            from transformers import AutoImageProcessor, AutoModelForSemanticSegmentation
        except ImportError as exc:
            raise RuntimeError('Semantic segmentation requires: pip install -r requirements-semantic.txt') from exc
        self.torch = torch
        self.processor = AutoImageProcessor.from_pretrained(self.model_id)
        self.model = AutoModelForSemanticSegmentation.from_pretrained(self.model_id)
        self.model.eval()
        self.labels = {int(k): v for k, v in self.model.config.id2label.items()}

    def predict(self, image):
        torch = self.torch
        pil = Image.fromarray(np.asarray(image, dtype=np.uint8))
        inputs = self.processor(images=pil, return_tensors='pt')
        with torch.no_grad():
            logits = self.model(**inputs).logits
            logits = torch.nn.functional.interpolate(
                logits, size=(pil.height, pil.width), mode='bilinear', align_corners=False)
            probabilities = torch.softmax(logits, dim=1)
            confidence, classes = probabilities.max(dim=1)
        return classes[0].cpu().numpy().astype(np.int32), confidence[0].cpu().numpy().astype(np.float32)

    def labels_present(self, class_map):
        return [(int(idx), self.labels.get(int(idx), f'class {idx}'))
                for idx in np.unique(class_map)]

    @staticmethod
    def selected_mask(class_map, confidence, class_ids, threshold=0.35):
        if not class_ids:
            return np.zeros(class_map.shape, dtype=bool)
        return np.isin(class_map, list(class_ids)) & (confidence >= threshold)


class MultiSizeExporter:
    """Generate an archive of independent, precomputed image sizes."""
    @staticmethod
    def build(image, sizes, method='Backward (gradient)', protection=None, progress=None):
        h, w = image.shape[:2]
        unique = list(dict.fromkeys((int(a), int(b)) for a, b in sizes))
        if not unique:
            raise ValueError('Select at least one target size')
        if len(unique) > 12:
            raise ValueError('Limit multi-size export to 12 variants per batch')
        for width, height in unique:
            if width < 1 or height < 1 or width > 2*w or height > 2*h:
                raise ValueError(f'Unsupported target size: {width}x{height}')
        from .core import SeamCarvingController, ImageDocument
        controller = SeamCarvingController()
        manifest = {'source_width': w, 'source_height': h, 'method': method,
                    'representation': 'independently precomputed PNG variants', 'variants': []}
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, 'w', zipfile.ZIP_DEFLATED) as archive:
            for i, (width, height) in enumerate(unique):
                result = controller.resize(ImageDocument(image), ResizeParameters(width, height, method), protection)
                name = f'variants/seam_{width}x{height}.png'
                archive.writestr(name, ImageExporter.png_bytes(result.image))
                manifest['variants'].append({'file': name, 'width': width, 'height': height,
                                             'seconds': round(result.seconds, 4)})
                if progress:
                    progress((i + 1) / len(unique))
            archive.writestr('manifest.json', json.dumps(manifest, indent=2))
        return stream.getvalue(), manifest
