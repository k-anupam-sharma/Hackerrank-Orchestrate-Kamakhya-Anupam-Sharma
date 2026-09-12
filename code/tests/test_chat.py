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

    def test_active_request_accepts_many_followups_without_reselection(self) -> None:
        chat = BuyOrWaitChat(ROOT / "dataset")
        chat.handle("select request_67")
        self.assertEqual("request_67", chat.active_request_id)
        first_context = chat.active_request_context
        first_result = chat.active_request_result
        questions = (
            "How much can I safely pay today?",
            "Why?",
            "What is my minimum balance?",
            "When can I pay the full amount?",
            "What payment options are available?",
            "What happens to my balance after paying today?",
        )
        for question in questions:
            with self.subTest(question=question):
                response, keep_running = chat.handle(question)
                self.assertTrue(keep_running)
                self.assertTrue(response.strip())
                self.assertEqual("request_67", chat.active_request_id)
                self.assertIs(first_context, chat.active_request_context)
                self.assertIs(first_result, chat.active_request_result)

    def test_switch_reset_and_question_without_active_request(self) -> None:
        chat = BuyOrWaitChat(ROOT / "dataset")
        chat.handle("select request_67")
        old_context = chat.active_request_context
        response, _ = chat.handle("select request_69")
        self.assertIn("ACTIVE REQUEST: request_69", response)
        self.assertEqual("request_69", chat.active_request_id)
        self.assertIsNot(old_context, chat.active_request_context)
        chat.handle("reset")
        no_context, keep_running = chat.handle("Can I afford this?")
        self.assertTrue(keep_running)
        self.assertIn("No request is selected", no_context)

    def test_sources_commands_and_natural_language_are_request_scoped(self) -> None:
        chat = BuyOrWaitChat(ROOT / "dataset")
        chat.handle("select request_67")
        active_sources, _ = chat.handle("sources")
        asked_sources, _ = chat.handle("What sources did you use?")
        other_sources, _ = chat.handle("sources request_69")
        self.assertIn("SOURCES FOR request_67", active_sources)
        self.assertIn("dataset/requests.csv", active_sources)
        self.assertIn("request_id: request_67", active_sources)
        self.assertIn("SOURCES FOR request_67", asked_sources)
        self.assertIn("SOURCES FOR request_69", other_sources)
        self.assertNotIn("request_id: request_67", other_sources)
        self.assertEqual("request_67", chat.active_request_id)
        active_event_ids = chat._affected_event_ids(chat.selected)
        for event_id in active_event_ids:
            self.assertEqual("user_67", chat.index.events_by_id[event_id].user_id)

    def test_event_message_and_debug_provenance_answers(self) -> None:
        chat = BuyOrWaitChat(ROOT / "dataset", debug=True)
        chat.handle("select request_69")
        events, _ = chat.handle("Which events affected the forecast?")
        messages, _ = chat.handle("Which message affected this decision?")
        debug, _ = chat.handle("debug")
        self.assertIn("FINANCIAL EVENTS", events)
        self.assertIn("message", messages.lower())
        self.assertIn("Active request: request_69", debug)
        self.assertIn("SOURCES FOR request_69", debug)

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
