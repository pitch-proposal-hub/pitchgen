from agents.base_agent import BaseAgent
from agents.workflows.agenda_workflow import AgendaWorkflow
from agents.workflows.outline_workflow import OutlineWorkflow


class AgendaAgent(BaseAgent):

  def __init__(self, config):
    super().__init__(
        "AgendaAgent",
        "Responsible for generating outlines and converting them to agendas.",
    )
    self.add_skill("outline", OutlineWorkflow(config))
    self.add_skill("agenda", AgendaWorkflow(config))

  def run(self, global_state):
    print(f"[{self.name}] Starting narrative strategy...")

    # 1. Generate Outline
    outline = self.skills["outline"].execute(global_state.context)
    global_state.outline = outline
    if "presentation_archetype" in outline:
      global_state.context["presentation_archetype"] = outline[
          "presentation_archetype"
      ]
    if "primary_anchor_deck_id" in outline:
      global_state.context["primary_anchor_deck_id"] = outline[
          "primary_anchor_deck_id"
      ]
      global_state.context["primary_anchor_deck_title"] = outline.get(
          "primary_anchor_deck_title", ""
      )
    if "industry" in outline:
      global_state.context["industry"] = outline["industry"]
    if "sub_industry" in outline:
      global_state.context["sub_industry"] = outline["sub_industry"]
    if "micro_industry" in outline:
      global_state.context["micro_industry"] = outline["micro_industry"]
    if "domain_lexicon" in outline:
      global_state.context["domain_lexicon"] = outline["domain_lexicon"]
    if "anchor_decks" in outline:
      global_state.context["anchor_decks"] = outline["anchor_decks"]
      global_state.context["anchor_deck_ids"] = outline.get(
          "anchor_deck_ids", []
      )
      global_state.context["anchor_deck_map"] = outline.get(
          "anchor_deck_map", {}
      )
    if "closest_industry" in outline:
      global_state.context["closest_industry"] = outline["closest_industry"]
    if "vertical_anchor" in outline:
      global_state.context["vertical_anchor"] = outline["vertical_anchor"]
    if "solution_anchors" in outline:
      global_state.context["solution_anchors"] = outline["solution_anchors"]
    if "required_sales_plays" in outline:
      global_state.context["required_sales_plays"] = outline["required_sales_plays"]
    if "is_s0_customer_discovery" in outline:
      global_state.context["is_s0_customer_discovery"] = outline[
          "is_s0_customer_discovery"
      ]

    # 2. Generate Agendas
    agendas = self.skills["agenda"].execute(outline)
    global_state.agendas = agendas

    print(f"[{self.name}] Narrative strategy completed.")
    return global_state
