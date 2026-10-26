import unittest
import numpy as np
from PIL import Image
from seamcarving import (BackwardEnergy, ForwardEnergy, SeamFinder, SeamEditor,
                         ImageDocument, ResizeParameters, SeamCarvingController,
                         ImageExporter, ImageResizer)

class SeamTests(unittest.TestCase):
    def setUp(self):
        self.image = np.random.default_rng(42).integers(0,256,(9,12,3),dtype=np.uint8)

    def test_seam_is_connected(self):
        for method in (BackwardEnergy(), ForwardEnergy()):
            seam = method.find_seam(self.image)
            self.assertEqual(seam.shape, (9,))
            self.assertTrue(np.all(np.abs(np.diff(seam)) <= 1))

    def test_vertical_remove_and_insert(self):
        seam = BackwardEnergy().find_seam(self.image)
        self.assertEqual(SeamEditor.remove(self.image,seam).shape,(9,11,3))
        self.assertEqual(SeamEditor.insert(self.image,seam).shape,(9,13,3))

    def test_reduce_both_axes(self):
        doc = ImageDocument(self.image)
        res = SeamCarvingController().resize(doc,ResizeParameters(8,6))
        self.assertEqual(res.image.shape,(6,8,3))
        self.assertEqual(res.seams_removed,7)
        self.assertTrue(np.array_equal(self.image,doc.original))

    def test_forward_and_protection(self):
        mask = np.zeros((9,12),dtype=bool)
        mask[:,3:6] = True
        doc = ImageDocument(self.image)
        res = SeamCarvingController().resize(doc,ResizeParameters(10,8,'Forward (transition)'),mask)
        self.assertEqual(res.image.shape,(8,10,3))

    def test_enlarge(self):
        doc = ImageDocument(self.image)
        res = SeamCarvingController().resize(doc,ResizeParameters(14,11))
        self.assertEqual(res.image.shape,(11,14,3))
        self.assertEqual(res.seams_inserted,4)

    def test_invalid_targets(self):
        for dims in ((0,4),(30,8)):
            with self.assertRaises(ValueError):
                SeamCarvingController().resize(ImageDocument(self.image),ResizeParameters(*dims))

    def test_png_export(self):
        import io
        raw = ImageExporter.png_bytes(self.image)
        restored = np.asarray(Image.open(io.BytesIO(raw)).convert('RGB'))
        np.testing.assert_array_equal(restored,self.image)

    def test_conventional_resize(self):
        self.assertEqual(ImageResizer.conventional(self.image,7,6).shape,(6,7,3))

if __name__ == '__main__':
    unittest.main()
