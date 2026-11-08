import unittest
from scripts.benchmark_search import reference


class SearchReferenceTests(unittest.TestCase):
    def test_twenty_natural_queries_have_bounded_measured_ranks_without_llm(self):
        report=reference()
        self.assertEqual(report['questions'],20)
        self.assertEqual(report['search_mode'],'lexical');self.assertFalse(report['nas_validation'])
        self.assertTrue(all(rank is None or 1<=rank<=3 for rank in report['ranks']))
        self.assertEqual(report['top_3'],sum(rank is not None for rank in report['ranks']))
