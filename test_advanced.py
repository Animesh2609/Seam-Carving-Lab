import io
import json
import unittest
import zipfile
import numpy as np
from PIL import Image
from seamcarving import ObjectRemovalService, MultiSizeExporter, SemanticSaliencyService

class AdvancedTests(unittest.TestCase):
    def setUp(self):
        self.image = np.random.default_rng(12).integers(0, 255, (12, 16, 3), dtype=np.uint8)

    def test_object_removal_and_restore(self):
        mask = np.zeros((12, 16), bool)
        mask[3:7, 7:10] = True
        result = ObjectRemovalService().remove(self.image, mask, restore_size=True)
        self.assertEqual(result.remaining_mask_pixels, 0)
        self.assertEqual(result.image.shape, self.image.shape)
        self.assertGreater(result.removed_vertical + result.removed_horizontal, 0)

    def test_object_removal_without_restore(self):
        mask = np.zeros((12, 16), bool)
        mask[2:5, 4:6] = True
        result = ObjectRemovalService().remove(self.image, mask, restore_size=False)
        self.assertEqual(result.remaining_mask_pixels, 0)
        self.assertLess(result.image.shape[0] * result.image.shape[1], 12*16)

    def test_overlapping_masks_rejected(self):
        mask = np.zeros((12,16), bool)
        mask[4:6,4:6] = True
        with self.assertRaises(ValueError):
            ObjectRemovalService().remove(self.image, mask, protection_mask=mask)

    def test_multi_size_zip(self):
        archive, manifest = MultiSizeExporter.build(self.image, [(12,12), (8,9)])
        self.assertEqual(len(manifest['variants']), 2)
        with zipfile.ZipFile(io.BytesIO(archive)) as z:
            self.assertIn('manifest.json', z.namelist())
            self.assertEqual(json.loads(z.read('manifest.json'))['source_width'], 16)
            self.assertEqual(Image.open(io.BytesIO(z.read('variants/seam_8x9.png'))).size, (8,9))

    def test_semantic_mask_selection(self):
        labels = np.array([[0, 1],[1, 2]])
        confidence = np.array([[0.9, 0.2],[0.8, 0.7]])
        mask = SemanticSaliencyService.selected_mask(labels, confidence, [1], 0.35)
        np.testing.assert_array_equal(mask, [[False,False],[True,False]])

if __name__ == '__main__':
    unittest.main()
