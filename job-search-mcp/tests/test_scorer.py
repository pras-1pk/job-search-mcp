import unittest

from tools.scorer import _extract_required_experience_years, _should_skip_for_experience


class ScorerTests(unittest.TestCase):
    def test_extract_required_experience_years_finds_minimum_requirement(self):
        text = "We are looking for 7+ years of backend engineering experience in Python and distributed systems."

        years = _extract_required_experience_years(text)

        self.assertEqual(years, 7)

    def test_should_skip_for_experience_mismatch_when_job_requires_more_than_resume(self):
        text = "Minimum 7 years of experience in backend APIs and cloud platforms."

        should_skip, reason = _should_skip_for_experience(resume_years=4, job_description=text)

        self.assertTrue(should_skip)
        self.assertIn("7", reason)

    def test_should_not_skip_when_job_requires_less_than_resume_experience(self):
        text = "3 to 5 years of backend engineering experience."

        should_skip, reason = _should_skip_for_experience(resume_years=4, job_description=text)

        self.assertFalse(should_skip)
        self.assertEqual(reason, "")


if __name__ == "__main__":
    unittest.main(verbosity=2)
