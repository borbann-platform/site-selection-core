"""
Unit tests for DAG decomposition and clarification loop.
"""

from langchain_core.messages import HumanMessage

from src.services.task_planner import TaskPlanner


def test_clarification_required_for_ambiguous_near_query():
    planner = TaskPlanner()
    messages = [HumanMessage(content="Find undervalued homes near top schools")]

    plan = planner.build_plan(messages, planner_llm=None)

    assert plan.requires_clarification is True
    assert len(plan.clarification_questions) > 0
    assert "reference_location" in plan.missing_constraints


def test_no_clarification_when_spatial_context_provided():
    planner = TaskPlanner()
    messages = [
        HumanMessage(
            content=(
                "Find undervalued homes near top schools\\n\\n"
                "[SPATIAL CONTEXT FROM MAP]\\n"
                "- PIN LOCATION: latitude=13.7563, longitude=100.5018"
            )
        )
    ]

    plan = planner.build_plan(messages, planner_llm=None)

    assert plan.requires_clarification is False
    assert len(plan.nodes) >= 1


def test_fallback_plan_is_dag():
    planner = TaskPlanner()
    messages = [
        HumanMessage(
            content="Compare district growth and rental yield trends for Sathorn vs Bang Kapi"
        )
    ]

    plan = planner.build_plan(messages, planner_llm=None)

    assert plan.requires_clarification is False
    ids = {node.id for node in plan.nodes}
    for node in plan.nodes:
        for dep in node.depends_on:
            assert dep in ids


def test_no_clarification_for_explicit_compare_targets():
    planner = TaskPlanner()
    messages = [
        HumanMessage(
            content="Compare Sathorn and Bang Kapi market trends for detached houses"
        )
    ]

    plan = planner.build_plan(messages, planner_llm=None)

    assert plan.requires_clarification is False
    assert len(plan.nodes) >= 1


def test_no_clarification_for_thai_compare_with_or_separator():
    planner = TaskPlanner()
    messages = [HumanMessage(content="เปรียบเทียบย่านอารีย์หรือสะพานควายสำหรับซื้อคอนโด")]

    plan = planner.build_plan(messages, planner_llm=None)

    assert plan.requires_clarification is False


def test_financial_prompt_does_not_trigger_compare_clarification():
    planner = TaskPlanner()
    messages = [
        HumanMessage(
            content="จะซื้อบ้าน 8 ล้าน เงินเดือน 80,000 ภาระผ่อนรถ 12,000 ช่วยคำนวณ DSR"
        )
    ]
    plan = planner.build_plan(messages, planner_llm=None)
    assert plan.requires_clarification is False
