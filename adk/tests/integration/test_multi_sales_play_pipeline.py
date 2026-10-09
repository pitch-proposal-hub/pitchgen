import pytest
import os
import sys
import json

# Setup import path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "src"))

from config_loader import load_config
from agents.workflows.outline_workflow import OutlineWorkflow
from agents.skill_loader import load_skill_instructions, load_skill_reference
from agents.workflows.isolated_sales_play_retriever import IsolatedSalesPlayRetriever
from agents.workflows.slide_retriever_factory import SlideRetrieverFactory

def test_sales_play_reference_files_exist():
    """Ensure all core Google Cloud sales play playbooks are present and non-empty."""
    required_playbooks = [
        "agentic_workplace_transformation.md",
        "gemini_enterprise_for_customer_experience.md",
        "scale_ai_apps_and_agents.md",
        "security_sales_plays.md",
        "agentic_data_cloud.md",
    ]
    for pb in required_playbooks:
        content = load_skill_reference("sales_play_selection", pb)
        assert content is not None, f"Missing sales play reference playbook: {pb}"
        assert len(content) > 100, f"Playbook {pb} content is too short"

def test_boost_spec_multi_play_formatting():
    """Verify IsolatedSalesPlayRetriever formats multi-play ANY(...) conditions correctly."""
    config = load_config()
    retriever = IsolatedSalesPlayRetriever(
        project_id=config["default"]["project_name"],
        datastore_id="test_datastore"
    )
    
    criteria = {
        "sales_play": [
            "Lead the Agentic Workplace Transformation",
            "Gemini Enterprise for Customer Experience",
            "Scale AI Apps and Agents",
            "Agentic Defense with Google Security"
        ],
        "practice_area": ["Agentic Workplace Transformation", "AI", "Security"]
    }
    
    boost_spec = retriever._build_boost_spec(criteria)
    conditions = [c.condition for c in boost_spec.condition_boost_specs]
    
    # Verify sales_play condition
    sp_cond = next((c for c in conditions if "sales_play: ANY(" in c), None)
    assert sp_cond is not None, "Missing sales_play ANY boost condition"
    assert '"Lead the Agentic Workplace Transformation"' in sp_cond
    assert '"Gemini Enterprise for Customer Experience"' in sp_cond
    assert '"Scale AI Apps and Agents"' in sp_cond
    assert '"Agentic Defense with Google Security"' in sp_cond
    
    # Verify practice_area condition
    pa_cond = next((c for c in conditions if "practice_area: ANY(" in c), None)
    assert pa_cond is not None, "Missing practice_area ANY boost condition"
    assert '"Agentic Workplace Transformation"' in pa_cond
    assert '"AI"' in pa_cond
    assert '"Security"' in pa_cond

def test_section1_reusable_retrieval():
    """Verify Section 1 (Current State / Market Trends) retrieves reusable slides from datastore."""
    config = load_config()
    ds_id = None
    key_to_use = "cloudhub_golden_sin"
    if "reusable" in config:
        for k in ["cloudhub_golden_sin", "pitch_sin", "sales_play_reusables"]:
            if k in config["reusable"] and config["reusable"][k]:
                ds_id = config["reusable"][k]
                key_to_use = k
                break

    if not ds_id:
        pytest.skip("No reusable slide datastore configured")

    retriever = SlideRetrieverFactory.get_retriever(key_to_use, ds_id, config)
    query = "Retail legacy data silos, market trends, customer friction, and inventory challenges"
    context = {
        "industry": "Retail",
        "salesPlay": ["Gemini Enterprise for Customer Experience", "Scale AI Apps and Agents"],
        "practice_area": ["AI"]
    }
    
    results = retriever.search_slides(query, context, limit=3)
    assert isinstance(results, list)
    assert len(results) > 0, "Expected at least 1 reusable slide result for Section 1 challenges query"
