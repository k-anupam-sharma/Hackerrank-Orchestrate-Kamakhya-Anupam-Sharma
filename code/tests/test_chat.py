"""Tests for the terminal chat presentation layer using the real dataset/solver."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from chat import BuyOrWaitChat, run_chat


class ChatTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.chat = BuyOrWaitChat(ROOT / "dataset")
        cls.request_id = next(iter(cls.chat.index.evaluation_requests_by_id))

    def test_startup_listing_and_help(self) -> None:
        response, keep_running = self.chat.handle("help")
        self.assertTrue(keep_running)
        self.assertIn("select <request_id>", response)
        listed, _ = self.chat.handle("list")
        self.assertIn(self.request_id, listed)

    def test_valid_and_invalid_selection(self) -> None:
        invalid, _ = self.chat.handle("select no_such_request")
        self.assertIn("Unknown evaluation request ID", invalid)
        selected, _ = self.chat.handle(f"select {self.request_id}")
        self.assertIn("AGENT DECISION", selected)
        self.assertEqual(self.request_id, self.chat.selected.result.request_id)

    def test_summary_plan_and_question_are_grounded(self) -> None:
        self.chat.select(self.request_id)
        for command in ("summary", "plan", "How much can I safely pay today?", "What payment method do you recommend?"):
            with self.subTest(command=command):
                response, keep_running = self.chat.handle(command)
                self.assertTrue(keep_running)
                self.assertTrue(response.strip())
        unsupported, _ = self.chat.handle("What will the stock market do next year?")
        self.assertIn("do not establish", unsupported)

    def test_reset_exit_and_scripted_loop(self) -> None:
        self.chat.select(self.request_id)
        reset, _ = self.chat.handle("reset")
        self.assertIn("Selection cleared", reset)
        goodbye, keep_running = self.chat.handle("exit")
        self.assertFalse(keep_running)
        self.assertEqual("Goodbye.", goodbye)
        inputs = iter(("help", "exit"))
        output: list[str] = []
        self.assertEqual(0, run_chat(BuyOrWaitChat(ROOT / "dataset"), input_fn=lambda _prompt: next(inputs), output_fn=output.append))
        self.assertTrue(any("BUY OR WAIT" in line for line in output))


if __name__ == "__main__":
    unittest.main()
