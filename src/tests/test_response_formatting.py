import unittest
from src.services.response_parsing import clean_structured_response, strip_code_fences


class TestResponseFormatting(unittest.TestCase):
    def test_strip_code_fences(self):
        raw = '```json\n{"text": "hello"}\n```'
        self.assertEqual(strip_code_fences(raw), '{"text": "hello"}')

    def test_clean_structured_response_converts_pipe_tables(self):
        markdown_table = """
| Time (Local) | Focus Area | Topics to Cover | Practical Exercise |
|--------------|------------|----------------|--------------------|
| **08:00 – 09:00** | **Planning & Review** | - Review yesterday’s objectives | Write a 5-minute summary |
| **09:00 – 10:30** | **Front-End Core** | - HTML5 semantic structure | Build a static landing page |
"""
        cleaned = clean_structured_response(markdown_table)
        self.assertNotIn("|", cleaned)
        self.assertIn("### **08:00 - 09:00**", cleaned)
        self.assertIn("* **Focus Area:** **Planning & Review**", cleaned)
        self.assertIn("* **Topics to Cover:** - Review yesterday's objectives", cleaned)
        self.assertIn("* **Practical Exercise:** Write a 5-minute summary", cleaned)

    def test_clean_structured_response_normalizes_hyphens(self):
        text_with_unicode_dash = "Front‑End – Core"
        cleaned = clean_structured_response(text_with_unicode_dash)
        self.assertNotIn("\u2011", cleaned)
        self.assertNotIn("\u2013", cleaned)
        self.assertIn("Front-End - Core", cleaned)


if __name__ == "__main__":
    unittest.main()
