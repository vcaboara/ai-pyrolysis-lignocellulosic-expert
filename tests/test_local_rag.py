import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from pyrolysis_lignocellulosic_ai_training.local_rag import (
    ChunkRecord,
    _chunk_records_from_rows,
    _source_type_for_path,
    answer_mode,
    build_context,
    build_index,
    fallback_answer,
    load_corpora,
    load_index,
    retrieve,
)


class LocalRagHelperTests(unittest.TestCase):
    def test_source_type_for_path_uses_filename_hints(self):
        self.assertEqual(_source_type_for_path(Path("/tmp/patent_alpha.jsonl")), "patent")
        self.assertEqual(_source_type_for_path(Path("/tmp/repo_beta.jsonl")), "repo")
        self.assertEqual(_source_type_for_path(Path("/tmp/other_data.jsonl")), "external")

    def test_chunk_records_from_rows_maps_fields(self):
        rows = [{"id": "1", "url": "https://example.com/a", "title": "Alpha", "text": "Pyrolysis text"}]

        records = _chunk_records_from_rows(rows, "patent")

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].chunk_id, "1")
        self.assertEqual(records[0].source_type, "patent")
        self.assertEqual(records[0].source_url, "https://example.com/a")
        self.assertEqual(records[0].title, "Alpha")
        self.assertEqual(records[0].text, "Pyrolysis text")

    def test_load_corpora_uses_path_type_and_ignores_missing_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            patent_path = root / "patent_chunks.jsonl"
            repo_path = root / "repo_chunks.jsonl"
            other_path = root / "misc_chunks.jsonl"

            patent_path.write_text(
                json.dumps(
                    {"id": "p1", "url": "https://patent.example/1", "title": "Patent", "text": "Biomass pyrolysis"}
                )
                + "\n",
                encoding="utf-8",
            )
            repo_path.write_text(
                json.dumps({"id": "r1", "url": "https://repo.example/1", "title": "Repo", "text": "Gas cleanup"})
                + "\n",
                encoding="utf-8",
            )
            other_path.write_text(
                json.dumps(
                    {"id": "e1", "url": "https://external.example/1", "title": "External", "text": "Thermal conversion"}
                )
                + "\n",
                encoding="utf-8",
            )

            records = load_corpora([patent_path, repo_path, other_path, root / "missing.jsonl"])

        self.assertEqual(len(records), 3)
        self.assertEqual([r.source_type for r in records], ["patent", "repo", "external"])

    def test_build_and_load_index_roundtrip(self):
        records = [
            ChunkRecord("1", "patent", "https://a", "Pyrolysis reactor", "Pyrolysis of biomass improves conversion."),
            ChunkRecord("2", "repo", "https://b", "Reactor notes", "Heat recovery and gas cleaning."),
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            index_dir = Path(tmpdir) / "index"
            build_index(records, index_dir)
            vectorizer, matrix, loaded = load_index(index_dir)

        self.assertIsNotNone(vectorizer)
        self.assertIsNotNone(matrix)
        self.assertEqual(len(loaded), 2)
        self.assertEqual(loaded[0].chunk_id, "1")
        self.assertEqual(loaded[1].source_type, "repo")

    def test_retrieve_filters_by_source_and_dedupes_urls(self):
        records = [
            ChunkRecord("1", "patent", "https://a", "Pyrolysis reactor", "Biomass pyrolysis is efficient."),
            ChunkRecord("2", "patent", "https://a", "Duplicate patent", "This is the same source URL."),
            ChunkRecord("3", "repo", "https://b", "Repo addendum", "Biochar and gas cleanup details."),
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            index_dir = Path(tmpdir) / "index"
            build_index(records, index_dir)
            vectorizer, matrix, _ = load_index(index_dir)
            hits = retrieve(
                query="pyrolysis biomass",
                vectorizer=vectorizer,
                matrix=matrix,
                records=records,
                top_k=3,
                external_boost=0.0,
                dedupe_sources=True,
                mode="answer",
                source_filter="patent",
            )

        self.assertTrue(all(item[1].source_type == "patent" for item in hits))
        self.assertEqual(len({item[1].source_url for item in hits}), len(hits))
        self.assertLessEqual(len(hits), 2)

    def test_retrieve_dedupe_still_holds_during_fallback_fill(self):
        records = [
            ChunkRecord("1", "patent", "https://a", "Alpha", "Pyrolysis process detail."),
            ChunkRecord("2", "patent", "https://a", "Duplicate alpha", "Same source URL."),
            ChunkRecord("3", "patent", "https://b", "Bravo", "Biochar gas cleanup detail."),
            ChunkRecord("4", "patent", "https://c", "Charlie", "Conversion reactor design."),
            ChunkRecord("5", "patent", "https://d", "Delta", "Feedstock pretreatment."),
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            index_dir = Path(tmpdir) / "index"
            build_index(records, index_dir)
            vectorizer, matrix, _ = load_index(index_dir)
            hits = retrieve(
                query="pyrolysis biomass",
                vectorizer=vectorizer,
                matrix=matrix,
                records=records,
                top_k=4,
                external_boost=0.0,
                dedupe_sources=True,
                mode="answer",
                source_filter="patent",
            )

        self.assertEqual(len({item[1].source_url for item in hits}), len(hits))
        self.assertLessEqual(len(hits), 4)

    def test_retrieve_dedupe_collapses_to_single_hit_when_same_url_repeats(self):
        records = [
            ChunkRecord("1", "patent", "https://same-source", "Primary", "Pyrolysis process detail."),
            ChunkRecord("2", "patent", "https://same-source", "Duplicate", "Same source URL."),
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            index_dir = Path(tmpdir) / "index"
            build_index(records, index_dir)
            vectorizer, matrix, _ = load_index(index_dir)
            hits = retrieve(
                query="pyrolysis biomass",
                vectorizer=vectorizer,
                matrix=matrix,
                records=records,
                top_k=2,
                external_boost=0.0,
                dedupe_sources=True,
                mode="answer",
                source_filter="patent",
            )

        self.assertEqual(len(hits), 1)
        self.assertEqual({item[1].source_url for item in hits}, {"https://same-source"})

    def test_build_context_and_answer_fallback_include_citations(self):
        hits = [(0.9, ChunkRecord("1", "patent", "https://a", "Patent title", "A long pyrolysis description."))]

        context, refs = build_context(hits)
        self.assertIn("[S1]", context)
        self.assertEqual(refs[0]["ref"], "S1")
        self.assertEqual(refs[0]["url"], "https://a")

        fallback = fallback_answer("What is pyrolysis?", refs, hits)
        self.assertIn("What is pyrolysis?", fallback)
        self.assertIn("[S1]", fallback)

        response = answer_mode(
            question="What is pyrolysis?",
            context=context,
            refs=refs,
            model="dummy",
            use_llm=False,
            hits=hits,
        )
        self.assertIn("Most relevant evidence:", response)
        self.assertIn("Citations:", response)


ROOT = Path(__file__).resolve().parents[1]
RUN_LOCAL_CI_PATH = ROOT / "run_local_ci.py"
RUN_LOCAL_CI_SPEC = importlib.util.spec_from_file_location("run_local_ci", RUN_LOCAL_CI_PATH)
assert RUN_LOCAL_CI_SPEC is not None
assert RUN_LOCAL_CI_SPEC.loader is not None
run_local_ci = importlib.util.module_from_spec(RUN_LOCAL_CI_SPEC)
RUN_LOCAL_CI_SPEC.loader.exec_module(run_local_ci)


class RunLocalCiCliTests(unittest.TestCase):
    def test_parse_args_supports_fix_format_flag(self):
        args = run_local_ci.parse_args(["--fix-format"])
        self.assertTrue(args.fix_format)
        self.assertFalse(args.format)

    def test_main_with_all_does_not_trigger_fix_format(self):
        check_modes = []
        dep_audit_called = False

        def fake_run_tests():
            return 0

        def fake_run_privacy():
            return 0

        def fake_run_format(check_only=True):
            check_modes.append(check_only)
            return 0

        def fake_run_lint():
            return 0

        def fake_run_mypy():
            return 0

        def fake_run_deps_audit():
            nonlocal dep_audit_called
            dep_audit_called = True
            return 0

        def fake_run_compose():
            return 0

        def fake_run_security():
            return 0

        with (
            mock.patch.object(run_local_ci, "run_tests", side_effect=fake_run_tests),
            mock.patch.object(run_local_ci, "run_security", side_effect=fake_run_security),
            mock.patch.object(run_local_ci, "run_privacy_scan", side_effect=fake_run_privacy),
            mock.patch.object(run_local_ci, "run_format", side_effect=fake_run_format),
            mock.patch.object(run_local_ci, "run_lint", side_effect=fake_run_lint),
            mock.patch.object(run_local_ci, "run_mypy", side_effect=fake_run_mypy),
            mock.patch.object(run_local_ci, "run_deps_audit", side_effect=fake_run_deps_audit),
            mock.patch.object(run_local_ci, "run_compose_check", side_effect=fake_run_compose),
        ):
            exit_code = run_local_ci.main_for_tests(["--all"])

        self.assertEqual(exit_code, 0)
        self.assertIn(True, check_modes)
        self.assertNotIn(False, check_modes)
        self.assertTrue(dep_audit_called)

    def test_parse_args_supports_deps_audit_flag(self):
        args = run_local_ci.parse_args(["--deps-audit"])
        self.assertTrue(args.deps_audit)


if __name__ == "__main__":
    unittest.main()
