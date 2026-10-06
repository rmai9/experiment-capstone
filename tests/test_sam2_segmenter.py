import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np

from src.segmentation.sam2_segmenter import (
	_normalize_box,
	_save_masked_image,
)


class Sam2SegmenterTests(unittest.TestCase):
	def test_normalize_box_rejects_invalid_coordinates(self):
		with self.assertRaises(ValueError):
			_normalize_box((0.5, 0.2, 0.4, 0.8))

	def test_save_masked_image_writes_transparent_background(self):
		with tempfile.TemporaryDirectory() as directory:
			root = Path(directory)
			source = root / "frame_000030.jpg"
			output = root / "segmented" / "frame_000030.png"
			cv2.imwrite(str(source), np.full((2, 2, 3), 255, dtype=np.uint8))

			_save_masked_image(
				source,
				output,
				np.array([[True, False], [False, True]]),
			)

			result = cv2.imread(str(output), cv2.IMREAD_UNCHANGED)
			self.assertEqual(result.shape, (2, 2, 4))
			self.assertEqual(result[0, 0, 3], 255)
			self.assertEqual(result[0, 1, 3], 0)


if __name__ == "__main__":
	unittest.main()