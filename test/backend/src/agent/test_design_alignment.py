from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]


def test_original_design_document_is_preserved_as_utf8_markdown():
    design = ROOT / "docs" / "设计文档.md"

    assert design.exists()
    content = design.read_text(encoding="utf-8")
    assert "一、引言" in content
    assert "2.1 Agent服务" in content
    assert "四、代码要求" in content
    assert "不引入 deerflow 或 hermes" in content


def test_system_capabilities_match_current_agent_features(client):
    response = client.get("/api/system/capabilities")

    assert response.status_code == 200
    data = response.json()
    features = set(data["features"])
    assert {
        "llm_models",
        "streaming_dm",
        "context_summary",
        "world_events",
        "stories",
    }.issubset(features)
    assert all("offline template provider" not in item.lower() for item in data["limitations"])
