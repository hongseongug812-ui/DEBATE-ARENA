"""
test_history.py — DebateHistory 직렬화/역직렬화 테스트
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from main import DebateHistory, ConversationRound


def test_add_round_and_transcript():
    h = DebateHistory()
    h.topic = "스타트업 창업"

    r1 = ConversationRound("초기 의견")
    r1.add("optimist", "충분히 가능합니다.")
    r1.add("critic", "리스크가 큽니다.")
    h.add_round(r1)

    transcript = h.format_full_transcript()
    assert "Round 1" in transcript
    assert "낙관론자" in transcript
    assert "비판론자" in transcript
    assert "충분히 가능합니다." in transcript


def test_serialization_roundtrip():
    h = DebateHistory()
    h.topic = "테스트"

    r = ConversationRound("테스트 라운드")
    r.add("optimist", "긍정적입니다.")
    r.add("veteran", "경험상 힘듭니다.")
    h.add_round(r)

    serialized = h.to_serializable()
    restored = DebateHistory.from_serializable(serialized)

    assert len(restored.rounds) == 1
    assert restored.rounds[0].title == "테스트 라운드"
    assert restored.rounds[0].messages[0]["agent_id"] == "optimist"
    assert restored.rounds[0].messages[1]["text"] == "경험상 힘듭니다."


def test_round_format_for_next():
    r = ConversationRound("라운드")
    assert r.format_for_next() == ""

    r.add("optimist", "A입니다.")
    r.add("critic", "B입니다.")

    result = r.format_for_next()
    assert "낙관론자: A입니다." in result
    assert "비판론자: B입니다." in result


def test_multiple_rounds_transcript():
    h = DebateHistory()
    for i in range(3):
        r = ConversationRound(f"라운드 {i+1}")
        r.add("optimist", f"발언 {i+1}")
        h.add_round(r)

    transcript = h.format_full_transcript()
    assert "Round 1" in transcript
    assert "Round 2" in transcript
    assert "Round 3" in transcript
