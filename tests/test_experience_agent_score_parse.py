import unittest
import sqlite3

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

    def test_process_stream_skips_failed_experience_save(self) -> None:
        class FailingMemory:
            def add_experience(self, *args, **kwargs):
                raise sqlite3.OperationalError("database is locked")

        agent = ExperienceAgent.__new__(ExperienceAgent)
        agent.memory_manager = FailingMemory()
        agent._distill_process_log = lambda process_log: "distilled"
        agent._evaluate_experience = lambda instruction, distilled_log, result: 0.8
        agent._extract_long_term_memories = lambda instruction, distilled_log, result: []
        agent._save_long_term_memories = lambda memories, session_id=None: 0

        messages = list(
            agent.process_experience_stream(
                "thinking",
                "instruction",
                "process",
                "result",
                session_id="s1",
            )
        )

        self.assertTrue(any("保存经验失败" in message for message in messages))
        self.assertIn("[经验总结 Agent] 长期记忆已更新 (0 条)", messages)


if __name__ == "__main__":
    unittest.main()
