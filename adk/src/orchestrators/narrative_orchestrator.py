from agents.agenda_agent import AgendaAgent
from agents.retrieval_agent import RetrievalAgent
from state import GlobalState


class NarrativeOrchestrator:

  def __init__(self, config):
    self.config = config
    self.agenda_agent = AgendaAgent(config)
    self.retrieval_agent = RetrievalAgent(config)

  def run(self, initial_context):
    print("[NarrativeOrchestrator] Initializing Narrative Phase...")
    state = GlobalState()
    state.context = initial_context

    # 1. Agenda Agent
    state = self.agenda_agent.run(state)

    # 2. Retrieval Agent
    state = self.retrieval_agent.run(state)

    print("[NarrativeOrchestrator] Narrative Phase Completed.")
    return state
