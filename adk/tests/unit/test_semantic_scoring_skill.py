import os
import sys
import unittest
from unittest.mock import MagicMock, patch
import numpy as np

# Prepend the pitchgen directory and src/ to sys.path
pitchgen_dir = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
sys.path.insert(0, pitchgen_dir)
sys.path.insert(0, os.path.join(pitchgen_dir, "src"))

from agents.workflows.semantic_scoring_workflow import SemanticScoringWorkflow

class TestSemanticScoringSkill(unittest.TestCase):

  def setUp(self):
    self.config = {
        'default': {
            'project_name': 'mock-project',
            'region': 'global'
        }
    }
    self.mock_client = MagicMock()
    
    # Patch genai.Client
    self.client_patcher = patch('agents.workflows.semantic_scoring_workflow.genai.Client', return_value=self.mock_client)
    self.client_patcher.start()

    self.skill = SemanticScoringWorkflow(self.config)

  def tearDown(self):
    self.client_patcher.stop()

  def test_get_embeddings(self):
    # Setup mock return value for embed_content
    mock_emb1 = MagicMock()
    mock_emb1.values = [0.1, 0.2, 0.3]
    mock_response = MagicMock()
    mock_response.embeddings = [mock_emb1]
    self.mock_client.models.embed_content.return_value = mock_response

    embeddings = self.skill.get_embeddings(["test query"])

    self.assertEqual(len(embeddings), 1)
    np.testing.assert_array_almost_equal(embeddings[0], np.array([0.1, 0.2, 0.3]))
    self.mock_client.models.embed_content.assert_called_once_with(
        model='text-embedding-005',
        contents=["test query"]
    )

  def test_execute_with_missing_embeddings(self):
    # Mock embed_content for query and for missing slide description
    mock_query_emb = MagicMock()
    mock_query_emb.values = [1.0, 0.0, 0.0]
    
    mock_slide_emb = MagicMock()
    mock_slide_emb.values = [1.0, 0.0, 0.0]

    mock_response1 = MagicMock()
    mock_response1.embeddings = [mock_query_emb]

    mock_response2 = MagicMock()
    mock_response2.embeddings = [mock_slide_emb]

    # Set side effects for the consecutive embed_content calls
    self.mock_client.models.embed_content.side_effect = [mock_response1, mock_response2]

    query = "test query"
    slide_data = [
        {'desc': 'matching slide description', 'name': 'slide1'}
    ]

    results = self.skill.execute(query, slide_data)

    self.assertEqual(len(results), 1)
    self.assertAlmostEqual(results[0]['_semantic_score'], 1.0)
    self.assertGreater(results[0]['sim_score'], 0.7)
    self.assertEqual(self.mock_client.models.embed_content.call_count, 2)

if __name__ == '__main__':
  unittest.main()
