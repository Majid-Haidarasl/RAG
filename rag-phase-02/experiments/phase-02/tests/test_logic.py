"""Unit tests for the kit's pure logic (no Ollama needed).

Run:  python3 -m unittest discover -s experiments/phase-02/tests -v
"""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common import (DATA, extract_json, fact_hits, normalize, read_jsonl, recall_at_k,  # noqa: E402
                    reciprocal_rank, render, strip_think)
from run_llm_test import is_refusal, validate_schema, CITE_RE  # noqa: E402


class TestNormalize(unittest.TestCase):
    def test_persian_digits_and_separators(self):
        self.assertEqual(normalize("۸٬۴۷۰ میلیون"), "8470 میلیون")
        self.assertEqual(normalize("۷۸٫۸"), "78.8")
        self.assertEqual(normalize("8,470"), "8470")

    def test_zwnj_and_arabic_letters(self):
        self.assertEqual(normalize("هیئت‌مدیره"), "هیئت مدیره")
        self.assertEqual(normalize("كيفيت"), "کیفیت")

    def test_arabic_comma_thousands(self):
        # qwen3 wrote "۸،۴۷۰" (U+060C) in run 20261109-184242; must equal 8470
        self.assertEqual(normalize("۸،۴۷۰ میلیون"), "8470 میلیون")
        self.assertEqual(normalize("1،2"), "1،2")          # not a thousands group

    def test_percent(self):
        self.assertEqual(normalize("۱۵ ٪"), "15%")


class TestFacts(unittest.TestCase):
    def test_alternatives(self):
        h, n, missed = fact_hits("سود عملیاتی ۱٬۱۷۰ میلیون تومان بود", [["1170"], ["13.8"]])
        self.assertEqual((h, n, missed), (1, 2, ["13.8"]))

    def test_empty(self):
        self.assertEqual(fact_hits("x", None), (0, 0, []))


class TestJson(unittest.TestCase):
    def test_plain_fenced_embedded(self):
        self.assertEqual(extract_json('{"a": 1}')[0], {"a": 1})
        self.assertEqual(extract_json('```json\n{"a": 2}\n```')[0], {"a": 2})
        self.assertEqual(extract_json('Here: {"a": {"b": "}"}} done')[0], {"a": {"b": "}"}})

    def test_think_block_removed(self):
        self.assertEqual(extract_json('<think>{"no": 1}</think>{"yes": 1}')[0], {"yes": 1})
        self.assertEqual(strip_think("<think>abc</think>\nanswer"), "answer")

    def test_invalid(self):
        obj, err = extract_json("no json here")
        self.assertIsNone(obj)
        self.assertEqual(err, "no-parsable-json")


    def test_malformed_outer_object_is_not_valid(self):
        # run 20261109-191910 fa-prompt_only-r1: a stray quote broke the outer object;
        # the old parser returned the first inner sub-issue and called it valid JSON
        bad = '{"issue_id": "X", "sub_issues": [{"id": "A"}, {" "id": "B"}]}'
        obj, err = extract_json(bad)
        self.assertIsNone(obj)
        self.assertTrue(err.startswith(("malformed-json", "unterminated-json")))
        obj, err = extract_json('{"a": {"b": 1}')  # truncated
        self.assertIsNone(obj)
        self.assertEqual(err, "unterminated-json")
        self.assertEqual(extract_json('Here: {"a": 1} done')[0], {"a": 1})


class TestRetrievalMetrics(unittest.TestCase):
    def test_recall_mrr(self):
        ranked = ["a", "b", "c", "d"]
        self.assertEqual(recall_at_k(ranked, {"c"}, 1), 0.0)
        self.assertEqual(recall_at_k(ranked, {"c"}, 3), 1.0)
        self.assertAlmostEqual(reciprocal_rank(ranked, {"c"}), 1 / 3)
        self.assertEqual(reciprocal_rank(ranked, {"z"}), 0.0)


class TestSchemaAndPrompts(unittest.TestCase):
    def setUp(self):
        root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        with open(os.path.join(root, "config", "prompt-registry.json"), encoding="utf-8") as f:
            self.reg = json.load(f)

    def test_judge_schema(self):
        s = self.reg["schemas"]["judge_schema"]
        good = {"scores": {"faithfulness": 5, "completeness": 5, "citation": 4, "clarity": 5}, "total": 19,
                "verdict": "accept"}
        self.assertEqual(validate_schema(good, s), [])
        bad = dict(good, verdict="ok")
        self.assertTrue(validate_schema(bad, s))
        self.assertTrue(validate_schema({"scores": {"faithfulness": True}}, s))

    def test_render_requires_all_vars(self):
        with self.assertRaises(ValueError):
            render("{{a}} {{b}}", a=1)

    def test_every_prompt_has_id_version(self):
        for p in self.reg["prompts"]:
            self.assertTrue(p["id"] and p["version"] and p["task_type"])

    def test_refusal_and_citations(self):
        self.assertTrue(is_refusal("INSUFFICIENT_CONTEXT — ایمیل در متن نیست"))
        self.assertFalse(is_refusal("مرخصی ۲۶ روز است [fa-HR-005-c1]"))
        self.assertEqual(CITE_RE.findall("x [fa-HR-005-c1] y [en-ISS-024-c1]"), ["fa-HR-005-c1", "en-ISS-024-c1"])


class TestDecomposeScoring(unittest.TestCase):
    def test_coverage_independent_of_label_and_name_typos(self):
        from run_llm_test import score_decompose
        with open(DATA / "llm_cases.json", encoding="utf-8") as f:
            spec = json.load(f)["decompose"]
        root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        with open(os.path.join(root, "config", "prompt-registry.json"), encoding="utf-8") as f:
            schema = json.load(f)["schemas"]["decompose_schema"]
        subs = [{"id": "1", "title": "t", "domain": "HW", "suggested_executor": "فرزانه جوادی", "related_docs": ["AR-HW-012"], "rationale": "r"},
                {"id": "3", "title": "t", "domain": "HW", "suggested_executor": "فرزانه جوتادی", "related_docs": [], "rationale": "r"},
                {"id": "2", "title": "t", "domain": "FIN", "suggested_executor": "مهسا جلالی", "related_docs": [], "rationale": "r"}]
        rec = {"lang": "fa", "content": json.dumps({"issue_id": "AR-ISS-024", "sub_issues": subs}, ensure_ascii=False)}
        score_decompose(rec, spec, schema)
        self.assertEqual(rec["domain_recall"], 0.333)          # LEG label missing
        self.assertEqual(rec["executor_coverage"], 0.667)      # HW + LEG owners present, WIN missing
        self.assertEqual(rec["executor_name_errors"], ["فرزانه جوتادی"])


class TestData(unittest.TestCase):
    def test_gold_facts_exist_in_relevant_chunk(self):
        chunks = {c["chunk_id"]: c for c in read_jsonl(DATA / "chunks.jsonl")}
        for q in read_jsonl(DATA / "gold_questions.jsonl"):
            cid = q["relevant"][q["lang"]][0]
            h, n, missed = fact_hits(chunks[cid]["text"], q["expected_facts"])
            self.assertEqual(h, n, f"{q['qid']} missing {missed}")


if __name__ == "__main__":
    unittest.main()
