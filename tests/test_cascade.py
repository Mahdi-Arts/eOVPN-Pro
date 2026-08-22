"""
eOVPN-Pro Cascade Helper Unit Tests
تست‌های واحد کمک‌های خالص موتور اتصال آبشاری
"""

import unittest

from eovpn.cascade import (
    cascade_banner_meta,
    cascade_progress_fraction,
    cascade_reason_label,
    cascade_remaining_seconds,
)


class TestCascadeProgress(unittest.TestCase):
    """Tests for the pure progress math / تست‌های ریاضیات پیشرفت خالص."""

    def test_fraction_basic(self):
        self.assertAlmostEqual(cascade_progress_fraction(0, 2, 0.0, 10.0), 0.0)
        self.assertAlmostEqual(cascade_progress_fraction(0, 2, 5.0, 10.0), 0.25)
        self.assertAlmostEqual(cascade_progress_fraction(1, 2, 0.0, 10.0), 0.5)
        self.assertAlmostEqual(cascade_progress_fraction(1, 2, 10.0, 10.0), 1.0)

    def test_fraction_clamped(self):
        # elapsed beyond the attempt budget must never exceed 1.0
        # زمان سپری‌شده بیشتر از بودجه تلاش هرگز نباید از 1.0 فراتر رود
        self.assertLessEqual(cascade_progress_fraction(1, 2, 999.0, 10.0), 1.0)
        # negative elapsed is treated as zero / زمان منفی صفر در نظر گرفته می‌شود
        self.assertGreaterEqual(cascade_progress_fraction(0, 2, -5.0, 10.0), 0.0)

    def test_fraction_zero_total_safe(self):
        # total=0 must not divide by zero / تعداد صفر نباید تقسیم بر صفر کند
        self.assertEqual(cascade_progress_fraction(0, 0, 0.0, 10.0), 0.0)

    def test_remaining_seconds(self):
        self.assertEqual(cascade_remaining_seconds(100.0, 93.4), 7)
        self.assertEqual(cascade_remaining_seconds(100.0, 150.0), 0)  # never negative


class TestCascadeMeta(unittest.TestCase):
    """Tests for the banner metadata / تست‌های متادیتای بنر آبشار."""

    def test_banner_meta_format(self):
        self.assertEqual(cascade_banner_meta(2, 10, 7), "3/10  ·  7s left")
        # index beyond total is clamped to the last position
        # اندیس بیشتر از کل به آخرین جایگاه محدود می‌شود
        self.assertEqual(cascade_banner_meta(99, 5, 0), "5/5  ·  0s left")

    def test_reason_labels(self):
        self.assertEqual(cascade_reason_label("timeout"), "timed out")
        self.assertEqual(cascade_reason_label("auth"), "authentication failed")
        # unknown reasons pass through unchanged / دلایل ناشناخته بدون تغییر می‌مانند
        self.assertEqual(cascade_reason_label("weird"), "weird")


if __name__ == "__main__":
    unittest.main()
