from src.services.internal_knowledge import internal_knowledge_service


def test_internal_knowledge_project_lookup():
    result = internal_knowledge_service.query(
        "pet friendly benjakitti dog", "project_metadata", limit=3
    )
    assert result["count"] >= 1


def test_internal_knowledge_legal_lookup():
    result = internal_knowledge_service.query(
        "ผู้จัดการมรดก เงินมัดจำ", "legal_guidelines_th", limit=5
    )
    assert result["count"] >= 1
