"""Tests for image enhancement and the retry pipeline (no OCR model needed)."""

import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services import image_enhance  # noqa: E402
from app.services.receipt_pipeline import read_receipt  # noqa: E402


def faint_receipt(paper=(165, 150, 140), ink=(155, 138, 125), size=(900, 600)):
    """Blue-grey ink on blue-grey paper: text barely differs from the page."""
    height, width = size
    image = np.empty((height, width, 3), np.uint8)
    image[:] = paper
    for row in range(60, height - 60, 40):          # fake lines of text
        image[row:row + 14, 80:width - 80] = ink
    return image


def contrast(image):
    gray = image if image.ndim == 2 else image.mean(axis=2)
    low, high = np.percentile(gray, (2, 98))
    return float(high - low)


class Enhancement(unittest.TestCase):
    def test_faint_text_gets_much_more_contrast(self):
        source = faint_receipt()
        result = image_enhance.enhanced(source)
        self.assertEqual(result.dtype, np.uint8)
        self.assertEqual(result.ndim, 3)
        self.assertGreater(contrast(result), 4 * contrast(source))

    def test_light_text_on_dark_page_is_flipped(self):
        dark = 255 - faint_receipt(paper=(40, 45, 50), ink=(95, 100, 105))
        result = image_enhance.enhanced(dark)
        self.assertGreater(float(np.median(result)), 150)       # page ends up light

    def test_sizes_are_normalised(self):
        small = np.full((300, 200, 3), 200, np.uint8)
        huge = np.full((4000, 3000, 3), 200, np.uint8)
        self.assertEqual(max(image_enhance.fit_size(small).shape[:2]), image_enhance.MIN_SIDE)
        self.assertEqual(max(image_enhance.fit_size(huge).shape[:2]), image_enhance.MAX_SIDE)
        medium = np.full((1500, 900, 3), 200, np.uint8)
        self.assertIs(image_enhance.fit_size(medium), medium)

    def test_blank_image_does_not_crash(self):
        image_enhance.enhanced(np.full((800, 500, 3), 255, np.uint8))
        image_enhance.enhanced(np.zeros((800, 500, 3), np.uint8))


def fake_receipt(items, status, confidence=0.95):
    ocr = {"lines": [{"text": "x", "confidence": confidence}] * 5}
    receipt = {
        "items": [{"name": f"item{i}", "total_price": 1} for i in range(items)],
        "reconciliation": {"status": status},
    }
    return ocr, receipt


class RetryPipeline(unittest.TestCase):
    def run_pipeline(self, outcomes):
        """`outcomes` maps variant -> (ocr, receipt); returns (result, variants tried)."""
        tried = []

        def extract(_path, variant):
            tried.append(variant)
            return outcomes[variant][0]

        def parse(ocr):
            return next(receipt for o, receipt in outcomes.values() if o is ocr)

        ocr, receipt = read_receipt("img.jpg", extract, parse, variants=tuple(outcomes))
        return (ocr, receipt), tried

    def test_good_first_read_is_final(self):
        outcomes = {"original": fake_receipt(3, "ok"), "enhanced": fake_receipt(3, "ok")}
        (_, receipt), tried = self.run_pipeline(outcomes)
        self.assertEqual(tried, ["original"])
        self.assertEqual(len(receipt["items"]), 3)

    def test_failed_first_read_falls_back_to_next_variant(self):
        outcomes = {
            "original": fake_receipt(0, "failed"),
            "enhanced": fake_receipt(2, "ok"),
        }
        (_, receipt), tried = self.run_pipeline(outcomes)
        self.assertEqual(tried, ["original", "enhanced"])
        self.assertEqual(len(receipt["items"]), 2)

    def test_best_attempt_is_kept_when_none_is_trustworthy(self):
        outcomes = {
            "original": fake_receipt(1, "mismatch"),
            "enhanced": fake_receipt(3, "mismatch"),
        }
        (_, receipt), tried = self.run_pipeline(outcomes)
        self.assertEqual(tried, ["original", "enhanced"])
        self.assertEqual(len(receipt["items"]), 3)                 # best of a bad lot


if __name__ == "__main__":
    unittest.main()
