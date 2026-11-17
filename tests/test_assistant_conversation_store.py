"""Tests for local, character-scoped conversation history and explicit memories."""
import tempfile
import unittest
from pathlib import Path

from DyberPet.assistant.conversation_store import CompanionStore


class CompanionStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = CompanionStore(Path(self.temp.name) / "companion.sqlite3")

    def test_turns_are_atomic_and_character_scoped(self):
        self.store.append_turn("鲸鱼娘", "你好", "你好呀")
        self.store.append_turn("Doro", "汪", "Doro!")
        self.assertEqual(
            [(x["role"], x["content"]) for x in self.store.recent_messages("鲸鱼娘")],
            [("user", "你好"), ("assistant", "你好呀")],
        )
        self.assertEqual(len(self.store.recent_messages("Doro")), 2)

    def test_history_is_bounded_and_validated(self):
        for i in range(8):
            self.store.append_turn("鲸鱼娘", f"问题{i}", f"回答{i}")
        self.assertEqual(len(self.store.recent_messages("鲸鱼娘", limit=5)), 5)
        with self.assertRaises(ValueError):
            self.store.recent_messages("鲸鱼娘", limit=51)

    def test_memory_requires_explicit_add_and_deduplicates(self):
        one = self.store.add_memory("鲸鱼娘", "用户喜欢航天器仿真", importance=3)
        two = self.store.add_memory("鲸鱼娘", "用户喜欢航天器仿真", importance=2, pinned=True)
        self.assertEqual(one["id"], two["id"])
        self.assertEqual(len(self.store.list_memories("鲸鱼娘")), 1)
        self.assertTrue(self.store.list_memories("鲸鱼娘")[0]["pinned"])

    def test_memory_retrieval_uses_chinese_bigrams_and_character_scope(self):
        self.store.add_memory("鲸鱼娘", "用户正在研究卫星故障诊断", importance=3)
        self.store.add_memory("鲸鱼娘", "用户喜欢猫咪", importance=1)
        self.store.add_memory("Doro", "用户正在研究卫星故障诊断", importance=3)
        matches = self.store.search_memories("鲸鱼娘", "卫星故障诊断")
        self.assertEqual(matches[0]["content"], "用户正在研究卫星故障诊断")
        self.assertEqual(len(self.store.search_memories("Doro", "卫星故障诊断")), 1)

    def test_memory_context_is_bounded(self):
        self.store.add_memory("鲸鱼娘", "用户喜欢第一项事实", importance=3, pinned=True)
        self.store.add_memory("鲸鱼娘", "用户喜欢第二项事实", importance=3, pinned=True)
        context = self.store.memory_context("鲸鱼娘", "喜欢", max_chars=30)
        self.assertLessEqual(len(context), 30)

    def test_memory_delete_is_character_scoped(self):
        item = self.store.add_memory("鲸鱼娘", "不要跨角色泄漏", importance=2)
        self.assertFalse(self.store.delete_memory("Doro", item["id"]))
        self.assertTrue(self.store.delete_memory("鲸鱼娘", item["id"]))
        self.assertEqual(self.store.list_memories("鲸鱼娘"), [])

    def test_database_rejects_symlink(self):
        link = Path(self.temp.name) / "linked.sqlite3"
        try:
            link.symlink_to(self.store.path)
        except (OSError, NotImplementedError):
            self.skipTest("symlinks unavailable")
        with self.assertRaises(ValueError):
            CompanionStore(link)


if __name__ == "__main__":
    unittest.main()
