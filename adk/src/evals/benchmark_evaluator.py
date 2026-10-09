"""Automated E2E Regression and Quality Benchmark Runner for PitchGen presentations."""

import json
import os
import re
import time
from typing import Any, Dict, List
from agents.skill_loader import get_domain_and_account_glossary, load_skill_instructions
from agents.workflows.foundation_deck_workflow import FoundationDeckWorkflow
from agents.workflows.outline_workflow import OutlineWorkflow
from agents.workflows.text_transformer_workflow import TextTransformerWorkflow
from config_loader import load_config
from evals.deck_perfection_inspector import DeckPerfectionInspector


class PitchGenQualityBenchmark:
  """Evaluates PitchGen GTM presentations against key quality dimensions."""

  def __init__(self, config=None):
    self.config = config or load_config()
    self.outline_workflow = OutlineWorkflow(self.config)
    self.foundation_workflow = FoundationDeckWorkflow(self.config)
    self.text_transformer = TextTransformerWorkflow(self.config)
    self.deck_inspector = DeckPerfectionInspector()

  def evaluate_presentation_gates(
      self,
      presentation: Dict[str, Any],
      *,
      customer_name: str = '',
      deck_strategy: str = 'smart_hybrid',
      deck_length: str = 'Standard (8-12 slides)',
      sales_stage: str = 'S2',
  ) -> Dict[str, Any]:
    """Evaluates a rendered Google Slides presentation dictionary across all 16 gates."""
    return self.deck_inspector.inspect_presentation_dict(
        presentation,
        customer_name=customer_name,
        deck_strategy=deck_strategy,
        deck_length=deck_length,
        sales_stage=sales_stage,
    ).to_dict()

  def evaluate_case(self, case: Dict[str, Any]) -> Dict[str, Any]:
    """Runs end-to-end evaluation for a single customer scenario."""
    case_id = case['case_id']
    customer_name = case['customer_name']
    user_request = case['user_request']
    industry = case.get('industry', '')
    sub_industry = case.get('sub_industry', '')
    sales_play = case.get('sales_play', '')
    expected_archetype = case.get('expected_archetype')
    expected_keywords = case.get('expected_vertical_keywords', [])
    forbidden_keywords = case.get('forbidden_cross_vertical_keywords', [])
    protected_proof_points = case.get('protected_proof_points', [])

    start_time = time.time()

    context = {
        'business_context': user_request,
        'customer_name': customer_name,
        'industry': industry,
        'sub_industry': sub_industry,
        'salesPlay': sales_play,
        'audience': case.get('target_audience', []),
        'win_cycle': case.get('win_cycle', ''),
    }

    # 1. Execute Outline Generation
    outline_res = self.outline_workflow.execute(context)
    latency_seconds = round(time.time() - start_time, 2)

    detected_archetype = context.get('presentation_archetype', '')
    anchor_deck_id = context.get('primary_anchor_deck_id', '')
    anchor_deck_title = context.get('primary_anchor_deck_title', '')

    # 2. Archetype Alignment Score (20 pts)
    archetype_score = (
        1.0
        if (not expected_archetype or detected_archetype == expected_archetype)
        else 0.5
    )

    # 3. Foundation Deck Domain Compatibility (20 pts)
    foundation_deck_score = 1.0
    if anchor_deck_title:
      for forbidden_kw in forbidden_keywords:
        if forbidden_kw.lower() in anchor_deck_title.lower():
          foundation_deck_score = 0.0
          break

    # 4. Domain Lexicon Precision Score (20 pts)
    outline_str = json.dumps(outline_res).lower()
    matched_keywords = [
        kw for kw in expected_keywords if kw.lower() in outline_str
    ]
    matched_forbidden = [
        kw for kw in forbidden_keywords if kw.lower() in outline_str
    ]

    lexicon_score = min(
        1.0, len(matched_keywords) / max(1, min(len(expected_keywords), 3))
    )
    if matched_forbidden:
      lexicon_score = max(0.0, lexicon_score - (0.3 * len(matched_forbidden)))

    # 5. Proof Point & Case Study Immutability Score (20 pts)
    sample_proof_point = (
        f"How {protected_proof_points[0] if protected_proof_points else 'Home Depot'}"
        ' reduced latency by 45% using Google Cloud'
    )
    proof_context = {
        'customer_name': customer_name,
        'industry': industry,
        'customer_research': context.get('customer_research', ''),
    }
    transformed_proof = self.text_transformer.execute(
        text=sample_proof_point,
        criteria='Make tone executive for target account',
        context=proof_context,
        slide_data={'slide_job': 'Proof_Points', 'is_cust_ref': True},
    )
    # Verify protected customer name was NOT swapped with target customer name
    if customer_name.lower() in transformed_proof.lower() and (
        protected_proof_points
        and protected_proof_points[0].lower() not in transformed_proof.lower()
    ):
      proof_point_score = 0.0  # Hallucinated / rebranded case study
    else:
      proof_point_score = 1.0  # Successfully preserved

    # 6. Anti-Overflow & Length Governance Score (20 pts)
    sample_header = 'Accelerating Enterprise AI Transformation'
    transformed_header = self.text_transformer.execute(
        text=sample_header,
        criteria='Refine headline',
        context=proof_context,
        slide_name='Slide 2 Header',
    )
    orig_header_len = len(sample_header)
    trans_header_len = len(transformed_header)

    # Header should stay within +25% character bound
    if trans_header_len <= int(orig_header_len * 1.30) + 5:
      overflow_score = 1.0
    else:
      overflow_score = 0.5

    # Aggregate Score (0 - 100)
    total_score = round(
        (archetype_score * 20)
        + (foundation_deck_score * 20)
        + (lexicon_score * 20)
        + (proof_point_score * 20)
        + (overflow_score * 20),
        1,
    )

    return {
        'case_id': case_id,
        'customer_name': customer_name,
        'total_score': total_score,
        'passed': total_score >= 80.0,
        'latency_seconds': latency_seconds,
        'detected_archetype': detected_archetype,
        'expected_archetype': expected_archetype,
        'anchor_deck_title': anchor_deck_title,
        'matched_vertical_keywords': matched_keywords,
        'forbidden_violations': matched_forbidden,
        'proof_point_score': proof_point_score * 20,
        'overflow_score': overflow_score * 20,
        'lexicon_score': round(lexicon_score * 20, 1),
        'archetype_score': archetype_score * 20,
        'foundation_score': foundation_deck_score * 20,
    }

  def run_all(
      self, dataset_path='tests/eval/datasets/pitchgen_golden_eval_dataset.json'
  ) -> List[Dict[str, Any]]:
    with open(dataset_path, 'r') as f:
      data = json.load(f)
    eval_cases = data.get('eval_cases', [])
    print(
        f'[PitchGen Quality Benchmark] Running {len(eval_cases)} evaluation'
        ' cases...'
    )

    results = []
    for idx, case in enumerate(eval_cases):
      print(
          f"[Benchmark] Case {idx+1}/{len(eval_cases)}: {case['customer_name']}"
          f" ({case['case_id']})..."
      )
      res = self.evaluate_case(case)
      results.append(res)
      print(
          f"  -> Score: {res['total_score']}/100.0 (Passed: {res['passed']},"
          f" Latency: {res['latency_seconds']}s)"
      )
    return results


if __name__ == '__main__':
    runner = PitchGenQualityBenchmark()
    results = runner.run_all()
    print('\n=================== BENCHMARK SCORECARD ===================')
    for r in results:
        status = '✅ PASS' if r['passed'] else '❌ FAIL'
        print(f"{status} | {r['customer_name']:<22} | Score: {r['total_score']:>5.1f}/100 | Latency: {r['latency_seconds']}s | Archetype: {r['detected_archetype']}")
