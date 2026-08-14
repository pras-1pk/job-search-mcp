import unittest

from tools.crawler import LOCATION_KEYWORDS, _priority_weight, _score_relevance, load_company_targets


class CrawlerTests(unittest.TestCase):
    def test_location_keywords_boost_india_job_scores(self):
        text = "Backend Engineer role in Bengaluru, India"

        base_score = _score_relevance(text, ["backend engineer"])
        boosted_score = _score_relevance(text, ["backend engineer", *LOCATION_KEYWORDS])

        self.assertGreater(boosted_score, base_score)
        self.assertGreaterEqual(boosted_score, 4)

    def test_score_relevance_prioritises_role_keywords(self):
        text = "Backend Platform Engineer role for Python Backend Engineer and distributed pipelines on GCP"
        score = _score_relevance(text, ["backend platform engineer", "python backend engineer"])

        self.assertGreaterEqual(score, 4)

    def test_load_company_targets_reads_yaml_config(self):
        companies = load_company_targets()

        self.assertIsInstance(companies, list)
        self.assertGreater(len(companies), 0)
        self.assertIn("name", companies[0])
        self.assertIn("career_url", companies[0])

    def test_priority_weight_uses_high_priority_preferences(self):
        self.assertGreater(_priority_weight({"priority": "high"}), _priority_weight({"priority": "low"}))


if __name__ == "__main__":
    unittest.main(verbosity=2)
