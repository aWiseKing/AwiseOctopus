import unittest

from models.experience_agent import ExperienceAgent


class TestExperienceAgentScoreParse(unittest.TestCase):
    def setUp(self) -> None:
        self.agent = ExperienceAgent.__new__(ExperienceAgent)

    def test_extract_score_plain_float(self) -> None:
        self.assertEqual(self.agent._extract_score("0.8"), 0.8)

    def test_extract_score_with_think_block(self) -> None:
        text = "<think>分析一下</think>\n0.8"
        self.assertEqual(self.agent._extract_score(text), 0.8)

    def test_extract_score_with_think_multiline_and_prefix(self) -> None:
        text = "<think>line1\nline2</think>\n评分：0.2"
        self.assertEqual(self.agent._extract_score(text), 0.2)

    def test_extract_score_json_number(self) -> None:
        self.assertEqual(self.agent._extract_score('{"score": 1}'), 1.0)

    def test_extract_score_json_string(self) -> None:
        self.assertEqual(self.agent._extract_score('{"score": "0.5"}'), 0.5)

    def test_extract_score_first_number_wins(self) -> None:
        self.assertEqual(self.agent._extract_score("得分 0.8，但也可能是 0.2"), 0.8)

    def test_extract_score_out_of_range_is_none(self) -> None:
        self.assertIsNone(self.agent._extract_score("2.0"))


if __name__ == "__main__":
    unittest.main()

