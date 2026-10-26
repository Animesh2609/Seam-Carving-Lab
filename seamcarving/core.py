"""Content-aware image resizing. Educational implementation of Avidan & Shamir (2007).
Forward energy is a separate extension inspired by Rubinstein et al. (2008).
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
from time import perf_counter
import numpy as np
from PIL import Image


@dataclass(frozen=True)
class ResizeParameters:
    width: int
    height: int
    method: str = 'Backward (gradient)'
    protect_strength: float = 1_000_000.0


@dataclass
class ImageDocument:
    original: np.ndarray
    result: np.ndarray | None = None

    @property
    def dimensions(self):
        h, w = self.original.shape[:2]
        return w, h


@dataclass
class ProcessingResult:
    image: np.ndarray
    seconds: float
    seams_removed: int
    seams_inserted: int


class EnergyStrategy(ABC):
    @abstractmethod
    def energy(self, image: np.ndarray) -> np.ndarray:
        raise NotImplementedError

    @abstractmethod
    def find_seam(self, image: np.ndarray, penalty: np.ndarray | None = None) -> np.ndarray:
        raise NotImplementedError


class BackwardEnergy(EnergyStrategy):
    def energy(self, image):
        a = image.astype(np.float64)
        # Absolute RGB differences along both axes, with edge replication.
        left = np.concatenate((a[:, :1], a[:, :-1]), axis=1)
        right = np.concatenate((a[:, 1:], a[:, -1:]), axis=1)
        up = np.concatenate((a[:1], a[:-1]), axis=0)
        down = np.concatenate((a[1:], a[-1:]), axis=0)
        return np.abs(right - left).sum(axis=2) + np.abs(down - up).sum(axis=2)

    def find_seam(self, image, penalty=None):
        e = self.energy(image)
        if penalty is not None:
            e = e + penalty
        return SeamFinder.backward(e)


class ForwardEnergy(BackwardEnergy):
    """Transition costs account for edges introduced by seam removal.
    Uses RGB L1 color difference and forward transition costs.
    """
    def find_seam(self, image, penalty=None):
        a = image.astype(np.float64)
        h, w = a.shape[:2]
        if w == 1:
            return np.zeros(h, dtype=np.int32)
        cumulative = np.zeros((h, w), dtype=np.float64)
        parent = np.zeros((h, w), dtype=np.int32)
        if penalty is not None:
            cumulative[0] = penalty[0]
        for y in range(1, h):
            for x in range(w):
                left = a[y, max(0, x - 1)]
                right = a[y, min(w - 1, x + 1)]
                up = a[y - 1, x]
                cu = np.abs(right - left).sum()
                choices = [(cumulative[y-1, x] + cu, x)]
                if x > 0:
                    cl = cu + np.abs(up - left).sum()
                    choices.append((cumulative[y-1, x-1] + cl, x-1))
                if x < w-1:
                    cr = cu + np.abs(up - right).sum()
                    choices.append((cumulative[y-1, x+1] + cr, x+1))
                cost, previous = min(choices, key=lambda item: item[0])
                cumulative[y, x] = cost + (penalty[y, x] if penalty is not None else 0)
                parent[y, x] = previous
        return SeamFinder.backtrack(cumulative, parent)


class SeamFinder:
    @staticmethod
    def backtrack(cumulative, parent):
        h = cumulative.shape[0]
        seam = np.empty(h, dtype=np.int32)
        seam[-1] = int(np.argmin(cumulative[-1]))
        for y in range(h-1, 0, -1):
            seam[y-1] = parent[y, seam[y]]
        return seam

    @staticmethod
    def backward(energy):
        h, w = energy.shape
        cost = energy.astype(np.float64).copy()
        parent = np.zeros((h, w), dtype=np.int32)
        for y in range(1, h):
            for x in range(w):
                lo, hi = max(0, x-1), min(w, x+2)
                p = lo + int(np.argmin(cost[y-1, lo:hi]))
                cost[y, x] += cost[y-1, p]
                parent[y, x] = p
        return SeamFinder.backtrack(cost, parent)


class SeamEditor:
    @staticmethod
    def validate_seam(seam, h, w):
        if len(seam) != h or np.any(seam < 0) or np.any(seam >= w):
            raise ValueError('Invalid seam coordinates')
        if np.any(np.abs(np.diff(seam)) > 1):
            raise ValueError('Seam is not 8-connected')

    @staticmethod
    def remove(array, seam):
        h, w = array.shape[:2]
        if w <= 1:
            raise ValueError('Cannot remove the last column')
        SeamEditor.validate_seam(seam, h, w)
        mask = np.ones((h, w), dtype=bool)
        mask[np.arange(h), seam] = False
        return array[mask].reshape((h, w-1) + array.shape[2:])

    @staticmethod
    def insert(array, seam):
        h, w = array.shape[:2]
        SeamEditor.validate_seam(seam, h, w)
        out = np.empty((h, w+1) + array.shape[2:], dtype=array.dtype)
        for y, x in enumerate(seam):
            out[y, :x+1] = array[y, :x+1]
            neighbor = array[y, min(x+1, w-1)]
            value = (array[y, x].astype(np.float64) + neighbor.astype(np.float64))/2
            out[y, x+1] = value.astype(array.dtype)
            out[y, x+2:] = array[y, x+1:]
        return out

    @staticmethod
    def overlay(image, seam, color=(255, 30, 40)):
        result = image.copy()
        result[np.arange(image.shape[0]), seam] = color
        return result


class SeamCarvingService:
    def __init__(self, strategy: EnergyStrategy):
        self.strategy = strategy

    def resize(self, image, params, protection=None, progress=None):
        if image.ndim != 3 or image.shape[2] != 3 or image.dtype != np.uint8:
            raise ValueError('Image must be an RGB uint8 array')
        h, w = image.shape[:2]
        if params.width < 1 or params.height < 1:
            raise ValueError('Target dimensions must be positive')
        if params.width > 2*w or params.height > 2*h:
            raise ValueError('This implementation limits enlargement to 2x per dimension')
        if protection is not None and protection.shape != (h, w):
            raise ValueError('Protection mask dimensions must match the image')
        output = image.copy()
        mask = protection.copy() if protection is not None else None
        total = abs(params.width-w) + abs(params.height-h)
        done = removed = inserted = 0
        start = perf_counter()
        # Width first; for height, transpose both image and protection mask.
        for axis, target in ((1, params.width), (0, params.height)):
            if axis == 0:
                output = np.transpose(output, (1, 0, 2))
                if mask is not None:
                    mask = mask.T
            while output.shape[1] != target:
                penalty = mask.astype(np.float64)*params.protect_strength if mask is not None else None
                seam = self.strategy.find_seam(output, penalty)
                if output.shape[1] > target:
                    output = SeamEditor.remove(output, seam)
                    if mask is not None:
                        mask = SeamEditor.remove(mask, seam)
                    removed += 1
                else:
                    output = SeamEditor.insert(output, seam)
                    if mask is not None:
                        mask = SeamEditor.insert(mask, seam)
                    inserted += 1
                done += 1
                if progress is not None:
                    progress(done / max(total, 1))
            if axis == 0:
                output = np.transpose(output, (1, 0, 2))
                if mask is not None:
                    mask = mask.T
        return ProcessingResult(output, perf_counter()-start, removed, inserted)


class SeamCarvingController:
    STRATEGIES = {'Backward (gradient)': BackwardEnergy, 'Forward (transition)': ForwardEnergy}

    def resize(self, document, params, protection=None, progress=None):
        if params.method not in self.STRATEGIES:
            raise ValueError('Unknown energy strategy')
        service = SeamCarvingService(self.STRATEGIES[params.method]())
        result = service.resize(document.original, params, protection, progress)
        document.result = result.image
        return result

    def preview(self, document, method='Backward (gradient)', protection=None):
        if method not in self.STRATEGIES:
            raise ValueError('Unknown energy strategy')
        strategy = self.STRATEGIES[method]()
        penalty = protection.astype(float)*1e6 if protection is not None else None
        seam = strategy.find_seam(document.original, penalty)
        energy = BackwardEnergy().energy(document.original)
        return energy, SeamEditor.overlay(document.original, seam)


class ImageExporter:
    @staticmethod
    def png_bytes(image):
        import io
        buffer = io.BytesIO()
        Image.fromarray(image).save(buffer, format='PNG')
        return buffer.getvalue()


class ImageResizer:
    @staticmethod
    def conventional(image, width, height):
        return np.asarray(Image.fromarray(image).resize((width, height), Image.Resampling.LANCZOS))
