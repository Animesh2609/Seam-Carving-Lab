"""Tests for the independent uploaded-PNG mask fallback."""
import io
import unittest
import numpy as np
from PIL import Image
from semantic_masks import mask_from_png

class SemanticMaskTests(unittest.TestCase):
    def png(self, array):
        mem=io.BytesIO()
        Image.fromarray(np.array(array,dtype=np.uint8),'L').save(mem,format='PNG')
        return mem.getvalue()

    def test_white_selects_pixels(self):
        mask=mask_from_png(self.png([[0,255],[130,10]]),(2,2))
        self.assertEqual(int(mask.sum()),2)
        self.assertTrue(mask[0,1])
        self.assertFalse(mask[0,0])

    def test_nearest_resizing(self):
        mask=mask_from_png(self.png([[255,0],[0,0]]),(4,4))
        self.assertEqual(mask.shape,(4,4))
        self.assertEqual(int(mask.sum()),4)

    def test_empty_or_corrupt_rejected(self):
        with self.assertRaises(ValueError): mask_from_png(b'',(2,2))
        with self.assertRaises(ValueError): mask_from_png(b'not a PNG',(2,2))

    def test_reject_invalid_target(self):
        with self.assertRaises(ValueError): mask_from_png(self.png([[255]]),(0,4))

if __name__ == '__main__':unittest.main()
