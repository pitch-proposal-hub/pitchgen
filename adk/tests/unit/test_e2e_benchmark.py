"""Unit test wrapper for PitchGen Automated E2E Quality and Regression Benchmark."""

import pytest
from evals.benchmark_evaluator import PitchGenQualityBenchmark


def test_pitchgen_quality_benchmark_suite():
    """Runs automated benchmark across golden evaluation accounts."""
    from unittest.mock import MagicMock

    benchmark = PitchGenQualityBenchmark()

    def _mock_outline_execute(ctx):
        ctx['presentation_archetype'] = 'Executive_Vision_Thought_Leadership'
        ctx['primary_anchor_deck_id'] = 'TEMPLATE_DECK_SALES_PLAY_PLACEHOLDER_001'
        ctx['primary_anchor_deck_title'] = (
            'Agentic Workplace Transformation for Luxury & Omnichannel Retail'
        )
        return {
            'title': 'Giorgio Armani omnichannel clienteling vision',
            'agendas': {
                '1': {
                    'title': 'Elevating luxury clienteling across omnichannel ateliers',
                    'parts': [
                        'Personalized luxury clienteling and store associate workflows',
                        'Omnichannel inventory visibility across global boutiques',
                    ],
                }
            },
        }

    mock_resp = MagicMock()
    mock_resp.text = 'Enterprise AI transforms luxury retail operations'
    benchmark.outline_workflow.execute = _mock_outline_execute
    benchmark.text_transformer.generate_content_with_fallback = (
        lambda *a, **kw: mock_resp
    )

    # Test a representative retail scenario
    sample_case = {
        'case_id': 'luxury_retail_awt',
        'customer_name': 'Giorgio Armani',
        'industry': 'Retail',
        'sub_industry': 'Luxury & Fashion',
        'sales_play': 'Agentic Workplace Transformation',
        'target_audience': ['Chief Technology Officer', 'Head of Digital Transformation'],
        'win_cycle': 'S2',
        'user_request': 'Build an executive pitch for Giorgio Armani on how Agentic Workplace Transformation and Gemini Enterprise empower store associates and digital ateliers to personalize clienteling and automate inventory tracking.',
        'expected_archetype': 'Executive_Vision_Thought_Leadership',
        'expected_vertical_keywords': ['clienteling', 'omnichannel', 'luxury'],
        'forbidden_cross_vertical_keywords': ['fleet management', 'subsea cable'],
        'protected_proof_points': ["Lowe's", 'Home Depot', 'Carrefour']
    }

    result = benchmark.evaluate_case(sample_case)

    # Assertions for quality score, proof point preservation, and anti-overflow
    assert result['passed'] is True, f"Benchmark failed with score {result['total_score']}/100: {result}"
    assert result['proof_point_score'] == 20, "Proof point immutability violated!"
    assert result['overflow_score'] == 20, "Anti-overflow bounds violated!"
    assert result['latency_seconds'] < 120.0, f"Latency exceeded budget: {result['latency_seconds']}s"
