"""Explicit application context tests / تست بستر صریح وابستگی برنامه."""

import unittest

from eovpn.context import ApplicationContext


class TestApplicationContext(unittest.TestCase):
    def test_contexts_do_not_share_state(self):
        first = ApplicationContext()
        second = ApplicationContext()
        first.set("value", object())
        self.assertIsNotNone(first.get("value"))
        self.assertIsNone(second.get("value"))

    def test_discard_and_clear(self):
        context = ApplicationContext()
        context.set("one", 1)
        context.set("two", 2)
        context.discard("one")
        self.assertIsNone(context.get("one"))
        context.clear()
        self.assertIsNone(context.get("two"))


if __name__ == "__main__":
    unittest.main()
