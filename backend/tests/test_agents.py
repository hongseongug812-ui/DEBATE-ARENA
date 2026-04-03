"""
test_agents.py — 에이전트 설정 유효성 테스트
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from agents import AGENTS, JUDGE_PROMPT, CONVERGENCE_CHECK_SYSTEM

DEBATE_AGENTS = ["optimist", "critic", "realist", "businessman", "veteran"]
ALL_AGENTS = DEBATE_AGENTS + ["judge"]


def test_all_agents_exist():
    for agent_id in ALL_AGENTS:
        assert agent_id in AGENTS, f"에이전트 '{agent_id}' 없음"


def test_agent_required_fields():
    required = {"name", "name_en", "color", "system_prompt"}
    for agent_id, agent in AGENTS.items():
        for field in required:
            assert field in agent, f"{agent_id}: '{field}' 필드 없음"


def test_agent_system_prompts_not_empty():
    for agent_id, agent in AGENTS.items():
        assert len(agent["system_prompt"]) > 20, f"{agent_id}: system_prompt 너무 짧음"


def test_agent_colors_valid_hex():
    import re
    for agent_id, agent in AGENTS.items():
        assert re.match(r"^#[0-9a-fA-F]{6}$", agent["color"]), \
            f"{agent_id}: color '{agent['color']}' 형식 오류"


def test_agents_are_korean():
    for agent_id, agent in AGENTS.items():
        assert agent["name"], f"{agent_id}: name 비어있음"


def test_judge_prompt_has_placeholders():
    assert "{topic}" in JUDGE_PROMPT
    assert "{transcript}" in JUDGE_PROMPT


def test_convergence_check_has_json_instruction():
    assert "converged" in CONVERGENCE_CHECK_SYSTEM
    assert "JSON" in CONVERGENCE_CHECK_SYSTEM or "json" in CONVERGENCE_CHECK_SYSTEM.lower()


def test_debate_agents_distinct_names():
    names = [AGENTS[a]["name"] for a in DEBATE_AGENTS]
    assert len(names) == len(set(names)), "에이전트 이름 중복"


def test_debate_agents_distinct_colors():
    colors = [AGENTS[a]["color"] for a in DEBATE_AGENTS]
    assert len(colors) == len(set(colors)), "에이전트 컬러 중복"
