import unittest
from pathlib import Path

from tools.resume_parser import extract_resume_profile, extract_text_from_file


class ResumeParserTests(unittest.TestCase):
    def test_extract_text_from_txt_file(self):
        sample = Path(__file__).with_name("sample_resume.txt")
        text = extract_text_from_file(sample)

        self.assertIn("Python", text)
        self.assertIn("FastAPI", text)

    def test_extract_resume_profile(self):
        sample = Path(__file__).with_name("sample_resume.txt")
        profile = extract_resume_profile(sample)

        self.assertIn("Python", profile["skills"])
        self.assertGreaterEqual(profile["experience_years"], 0)
        self.assertTrue(profile["summary"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
