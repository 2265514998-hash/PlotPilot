"""本地工作区扫描工具函数单测。"""
from application.workspace.local_workspace_service import (
    _guess_chapter_number,
    _parse_chinese_numeral,
    _word_count,
)


def test_parse_chinese_numeral():
    assert _parse_chinese_numeral("18") == 18
    assert _parse_chinese_numeral("十二") == 12


def test_guess_chapter_number():
    assert _guess_chapter_number("第3章 初入宗门.txt", 1) == 3
    assert _guess_chapter_number("Chapter 7 - fight.md", 1) == 7
    assert _guess_chapter_number("readme.txt", 5) == 5


def test_word_count_cjk():
    assert _word_count("你好世界") == 4
