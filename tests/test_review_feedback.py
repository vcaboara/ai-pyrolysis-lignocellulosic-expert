import unittest

from pyrolysis_lignocellulosic_ai_training.google_patents_ingest import (
    collapse_repeated_token_spans,
)
from pyrolysis_lignocellulosic_ai_training.local_rag import _dedupe_signature


class ReviewFeedbackTests(unittest.TestCase):
    def test_collapse_repeated_token_spans_removes_triplicate_runs(self) -> None:
        text = "alpha beta gamma alpha beta gamma alpha beta gamma zeta"
        result = collapse_repeated_token_spans(text, min_span_tokens=3, max_span_tokens=20)
        self.assertEqual(result, "alpha beta gamma zeta")

    def test_dedupe_signature_is_bounded_and_stable(self) -> None:
        big_text = "word " * 5000
        sig = _dedupe_signature("patent", "https://example.com/patent", "Example title", big_text)
        self.assertLess(len(sig), 512)
        self.assertTrue(sig.startswith("patent|https://example.com/patent|example title|"))


if __name__ == "__main__":
    unittest.main()
