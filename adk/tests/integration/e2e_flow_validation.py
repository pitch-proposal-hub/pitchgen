import unittest
from unittest.mock import MagicMock, patch
from orchestrators.creative_orchestrator import CreativeOrchestrator
from orchestrators.narrative_orchestrator import NarrativeOrchestrator
from state import GlobalState


class MockE2E(unittest.TestCase):

  @patch('agents.workflows.outline_workflow.discoveryengine.SearchServiceClient')
  @patch('agents.workflows.outline_workflow.secretmanager.SecretManagerServiceClient')
  def test_golden_flow(self, mock_sec, mock_disc):
    print('\n[E2E Mock] Starting golden flow simulation...')

    # 1. Mock Config
    config = {
        'default': {
            'project_name': 'mock-proj',
            'gemini_model': 'mock-model',
            'gemini_model_1': 'mock-model',
            'gemini_model_2': 'mock-model',
        },
        'datastore': {'website': 'mock-id'},
        'bucket': {
            'content': 'mock-content-bucket',
            'template': 'mock-template-bucket',
        },
    }

    # 2. Setup Orchestrators
    narrative_orch = NarrativeOrchestrator(config)
    creative_orch = CreativeOrchestrator(config)

    # ... rest of the test ...
    # Setup mocks on the instantiated clients
    narrative_orch.agenda_agent.skills['outline'].sec_client = MagicMock()
    narrative_orch.agenda_agent.skills['outline'].discovery_client = MagicMock()

    # Mock Skill Executions
    narrative_orch.agenda_agent.skills['outline'].execute = MagicMock(
        return_value={'outline': ['item1', 'item2']}
    )
    narrative_orch.agenda_agent.skills['agenda'].execute = MagicMock(
        return_value={'1': {'title': 'Agenda 1'}, '2': {'title': 'Agenda 2'}}
    )
    narrative_orch.retrieval_agent.skills['search'].execute = MagicMock(
        return_value=[{'slide': 'data'}]
    )
    narrative_orch.retrieval_agent.skills['score'].execute = MagicMock(
        return_value=[{'slide': 'data', 'sim_score': 0.9}]
    )

    creative_orch.slide_agent.skills['synthesis'].execute = MagicMock(
        return_value={'1': 'New content'}
    )
    creative_orch.slide_agent.skills['mapping'].execute = MagicMock(
        return_value={'temp_url': 'url', 'placeholders': {}}
    )
    creative_orch.slide_agent.skills['customizer'].execute = MagicMock(
        return_value={'title': 'Mock Customized Slide'}
    )
    creative_orch.visual_agent.skills['synthesis'].execute = MagicMock(
        return_value='iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=='
    )
    creative_orch.visual_agent._upload_to_gcs = MagicMock(
        return_value=('gs://mock-content-bucket/gen/image.png', None)
    )

    # 4. Simulation
    initial_context = {
        'business_context': 'Test simulation',
        'visuals_requested': True,
    }

    print('Running Narrative Phase...')
    state = narrative_orch.run(initial_context)

    print('Running Creative Phase...')
    final_state = creative_orch.run(state)

    # 5. Validation
    self.assertIsNotNone(final_state.final_deck_structure)
    self.assertIn('visual_assets', final_state.context)
    print('Golden flow simulation completed successfully without errors!')


if __name__ == '__main__':
  unittest.main()
