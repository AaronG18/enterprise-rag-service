"""EPIC #4 / SUB 20: PII detection and redaction in answers and log records."""
from __future__ import annotations

import unittest

from ragserve.generation.pii import detect_pii, redact_record, redact_text

CASES = [
    ("jane.doe@example.com", "email"),
    ("13812345678", "phone_cn"),
    ("11010519491231002X", "national_id"),
    ("4111 1111 1111 1111", "card"),
]

CLEAN_TEXT = "Full-time employees accrue 15 working days of paid annual leave per calendar year."


class TestDetection(unittest.TestCase):
    def test_each_shape_is_detected(self):
        for value, kind in CASES:
            found = detect_pii("contact %s please" % value)
            self.assertIn(kind, found, "%s not detected" % kind)

    def test_clean_text_has_no_findings(self):
        self.assertEqual(detect_pii(CLEAN_TEXT), [])

    def test_clean_text_is_untouched(self):
        self.assertEqual(redact_text(CLEAN_TEXT), CLEAN_TEXT)


class TestRedaction(unittest.TestCase):
    def test_values_are_masked_not_deleted(self):
        """Full deletion destroys debuggability; masking keeps shape for support."""
        for value, _kind in CASES:
            masked = redact_text("contact %s please" % value)
            self.assertNotIn(value, masked)
            self.assertIn("contact", masked)
            self.assertIn("please", masked)

    def test_email_keeps_domain(self):
        masked = redact_text("write to jane.doe@example.com now")
        self.assertIn("example.com", masked)
        self.assertNotIn("jane.doe", masked)

    def test_card_keeps_last_four(self):
        masked = redact_text("card 4111 1111 1111 1111 expired")
        self.assertIn("1111", masked)
        self.assertNotIn("4111 1111 1111 1111", masked)

    def test_multiple_findings_in_one_text(self):
        masked = redact_text("mail jane.doe@example.com or call 13812345678")
        self.assertNotIn("jane.doe@example.com", masked)
        self.assertNotIn("13812345678", masked)


class TestRecordRedaction(unittest.TestCase):
    def test_log_record_fields_are_redacted(self):
        record = {
            "workflow_id": "wf-1",
            "query": "my email is jane.doe@example.com",
            "answer": "your id 11010519491231002X is stored",
            "chunk_ids": ["handbook-en-00:0000"],
        }
        cleaned = redact_record(record)
        self.assertNotIn("jane.doe@example.com", cleaned["query"])
        self.assertNotIn("11010519491231002X", cleaned["answer"])
        self.assertEqual(cleaned["chunk_ids"], record["chunk_ids"])
        self.assertEqual(cleaned["workflow_id"], "wf-1")

    def test_record_without_text_fields_is_safe(self):
        record = {"count": 3, "nested": {"a": 1}}
        self.assertEqual(redact_record(record), record)


if __name__ == "__main__":
    unittest.main()
