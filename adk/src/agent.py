import ast
import json
import os
import re
import sys
import uuid
from google.cloud import storage

# Remove any API keys from the environment to prevent the google-genai SDK
# from using them instead of standard Google Cloud IAM/ADC credentials.
os.environ.pop("GEMINI_API_KEY", None)
os.environ.pop("GOOGLE_API_KEY", None)
os.environ.pop("API_KEY", None)

# Ensure the current directory is in the path to resolve local imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from google.adk.agents.llm_agent import Agent
from config_loader import load_config
from orchestrators.narrative_orchestrator import NarrativeOrchestrator
from orchestrators.creative_orchestrator import CreativeOrchestrator
from state import GlobalState
from agents.agenda_agent import AgendaAgent
from agents.retrieval_agent import RetrievalAgent


def robust_json_loads(s: str) -> dict:
  s = s.strip()
  # 1. Fix missing closing braces
  open_braces = s.count("{")
  close_braces = s.count("}")
  if open_braces > close_braces:
    s += "}" * (open_braces - close_braces)

  # 2. Try standard json loads first
  try:
    return json.loads(s)
  except Exception:
    pass

  # 3. Try ast.literal_eval after quoting unquoted keys
  try:
    temp = s
    # Quote unquoted keys (e.g. { user_inputs: -> { 'user_inputs': )
    temp = re.sub(r"([{,]\s*)([a-zA-Z_][a-zA-Z0-9_]*)(\s*:)", r"\1'\2'\3", temp)
    return ast.literal_eval(temp)
  except Exception as e:
    try:
      # Fallback: replace single quotes with double quotes and quote keys
      fallback_str = s.replace("'", '"')
      fallback_str = re.sub(
          r"([{,]\s*)([a-zA-Z_][a-zA-Z0-9_]*)(\s*:)", r'\1"\2"\3', fallback_str
      )
      return json.loads(fallback_str)
    except Exception:
      raise e


def execute_gcs_translation(payload: dict) -> dict:
  print("[PitchGenSkills] Starting GCS-based slide translation...")
  config = load_config()
  project_id = config["default"].get("project_name", os.getenv("GOOGLE_CLOUD_PROJECT", "YOUR_PROJECT_ID"))
  presentation_id = payload.get("presentationId")
  if not presentation_id:
    for k in payload.keys():
      if k not in [
          "presentationId",
          "targetLanguage",
          "isFullDeckTranslation",
          "action",
          "user_ldap",
      ]:
        presentation_id = k
        break
  if not presentation_id:
    presentation_id = "unknown"

  unique_id = str(uuid.uuid4())
  request_bucket_name = "translation-uploads-uat"
  request_blob_name = f"{presentation_id}_{unique_id}_Request.json"
  request_gcs_url = f"gs://{request_bucket_name}/{request_blob_name}"

  print(
      "[PitchGenSkills] Uploading request payload to GCS URL:"
      f" {request_gcs_url}..."
  )
  storage_client = storage.Client(project=project_id)
  req_bucket = storage_client.bucket(request_bucket_name)
  req_blob = req_bucket.blob(request_blob_name)
  req_blob.upload_from_string(
      json.dumps(payload, indent=2), content_type="application/json"
  )

  print("[PitchGenSkills] Executing TranslationWorkflow...")
  from agents.workflows.translation_workflow import TranslationWorkflow

  skill = TranslationWorkflow(config)
  response_gcs_url = skill.execute(request_gcs_url)
  print(
      f"[PitchGenSkills] Translation complete. Response URL: {response_gcs_url}"
  )

  return {
      "data": {"request": request_gcs_url, "response": response_gcs_url},
      "message": "Success",
  }


def dispatch_payload(payload_json: str, default_action: str = None) -> str:
  print(
      "[PitchGenSkills] Dispatching payload"
      f" (default_action={default_action})..."
  )
  try:
    payload = robust_json_loads(payload_json)
  except Exception as e:
    return json.dumps({"error": f"Failed to parse JSON payload: {str(e)}"})

  # 1. Check if it's a Slide Search request
  if "search_query" in payload:
    print("[PitchGenSkills] Routed to sidebar_search")
    return PitchGenSkills.sidebar_search(
        search_query=payload.get("search_query"),
        strict_search=payload.get("strict_search", False),
        user_ldap=payload.get("user_ldap", ""),
    )

  # 2. Check if it's a Sidebar Generate request
  if "slide_content" in payload or payload.get("action") == "add_generate":
    print("[PitchGenSkills] Routed to sidebar_generate")
    return PitchGenSkills.sidebar_generate(
        slide_content=payload.get("slide_content", payload.get("slide_content","")),
        slide_title=payload.get("slide_title", ""),
        slide_layout=payload.get("slide_layout", ""),
        slide_category=payload.get("slide_category", ""),
        deck_id=payload.get("deck_id", ""),
        slide_id=payload.get("slide_id", ""),
        audience=payload.get("audience", ""),
        industry=payload.get("industry", ""),
        product=payload.get("product", ""),
        region=payload.get("region", "GLOBAL"),
        action=payload.get("action", "add_generate"),
        er_number=payload.get("er_number", "21212"),
        user_ldap=payload.get("user_ldap", ""),
        presentation_id=payload.get("presentation_id", ""),
        slide_image_url=payload.get("slide_image_url", ""),
    )

  # 3. Check if it's a Visual Generation / Transformation request
  if "user_inputs" in payload or "existing_slide_image_url" in payload:
    print("[PitchGenSkills] Routed to generate_visual_payload")
    try:
      from agents.visual_agent import VisualAgent

      config = load_config()
      agent = VisualAgent(config)
      result = agent.run_payload(payload)
      return json.dumps(result)
    except Exception as e:
      return json.dumps({"error": str(e)})

  # Check if it's a Phase 2 Slide Generator request
  if "agendas" in payload:
    print("[PitchGenSkills] Routed to slide_generator_skill")
    return PitchGenSkills.slide_generator_skill(payload_json)

  # 4. Check if it's an Outline / Agenda generation request
  if "business_context" in payload:
    print("[PitchGenSkills] Routed to create_proposal_outline")
    sol = payload.get("solution") or payload.get("solutions") or ""
    if isinstance(sol, list):
      sol = ", ".join(sol)
    aud = payload.get("audience") or ""
    if isinstance(aud, list):
      aud = ", ".join(aud)
    prod = payload.get("product") or ""
    if isinstance(prod, list):
      prod = ", ".join(prod)
    sales_play = payload.get("salesPlay") or ""
    if isinstance(sales_play, list):
      sales_play = ", ".join(sales_play)

    return PitchGenSkills.create_proposal_outline(
        customer_name=payload.get("customer_name", ""),
        business_context=payload.get("business_context", ""),
        industry=payload.get("industry", ""),
        solution=sol,
        user_ldap=payload.get("user_ldap", ""),
        er_number=payload.get("er_number") or payload.get("erIdGenerate") or "",
        audience=aud,
        region=payload.get("region", ""),
        product=prod,
        request_type=payload.get("request_type", ""),
        presentation_id=payload.get("presentation_id", ""),
        salesPlay=sales_play,
        user_input_id=payload.get("user_input_id", ""),
        sub_industry=payload.get("sub_industry", ""),
    )

  # 5. Default Fallback Routing based on action or default_action
  action = payload.get("action") or default_action
  if action == "translate" or "presentationId" in payload:
    print("[PitchGenSkills] Routed to GCS slide translation flow")
    try:
      res = execute_gcs_translation(payload)
      return json.dumps(res)
    except Exception as e:
      return json.dumps({"error": str(e)})

  if action == "transform":
    print("[PitchGenSkills] Routed to transform_slide_payload")
    try:
      from agents.slide_engineering_agent import SlideEngineeringAgent

      config = load_config()
      agent = SlideEngineeringAgent(config)
      payload["action"] = "transform"
      result = agent.run_payload(payload)
      return json.dumps(result)
    except Exception as e:
      return json.dumps({"error": str(e)})

  return json.dumps({
      "error": f"Unknown payload format or action. Keys: {list(payload.keys())}"
  })


class PitchGenSkills:

  @staticmethod
  def create_proposal_outline(
      business_context: str,
      customer_name: str = "",
      industry: str = "",
      solution: str = "",
      user_ldap: str = "",
      er_number: str = "",
      audience: str = "",
      region: str = "",
      product: str = "",
      request_type: str = "",
      presentation_id: str = "",
      salesPlay: str = "",
      user_input_id: str = "",
      sub_industry: str = "",
  ) -> str:
    """Phase 1: Generates the initial outline and agendas based on customer context.

    Args:
        business_context: The business context or goal for the pitch.
        customer_name: The name of the target customer (e.g., 'Acme Corp').
        industry: The industry of the customer.
        solution: The proposed solutions or products, separated by commas.
        user_ldap: LDAP of the user.
        er_number: Opportunity ER number.
        audience: Target audience list, comma separated.
        region: Target region.
        product: Specific Google products list, comma separated.
        request_type: Request type (e.g., 'Full Deck').
        presentation_id: Active Slides Presentation ID.
        salesPlay: Name of the Sales Play if applicable.
        user_input_id: Unique generated session ID.
        sub_industry: Sub-industry name if applicable.

    Returns:
        A serialized GlobalState JSON string containing outline and agendas.
    """
    business_context_str = str(business_context).strip()
    if business_context_str.startswith("{"):
      return dispatch_payload(business_context_str)

    print(
        "[PitchGenSkills] Generating outline for customer:"
        f" '{customer_name}'..."
    )
    config = load_config()

    if not user_input_id or user_input_id == "":
      user_input_id = str(uuid.uuid4())

    solution_list = (
        [s.strip() for s in solution.split(",") if s.strip()]
        if solution
        else []
    )

    if isinstance(salesPlay, list):
      sales_play_list = salesPlay
    elif isinstance(salesPlay, str):
      sales_play_list = (
          [p.strip() for p in salesPlay.split(",") if p.strip()]
          if salesPlay
          else []
      )
    else:
      sales_play_list = []

    initial_context = {
        "customer_name": customer_name,
        "business_context": business_context,
        "industry": industry,
        "sub_industry": sub_industry,
        "solution": solution_list,
        "visuals_requested": True,
        # Store DB fields in context so they propagate to Phase 2
        "user_ldap": user_ldap,
        "er_number": er_number,
        "audience": audience.split(",") if audience else [],
        "region": region,
        "product": product.split(",") if product else [],
        "request_type": request_type,
        "presentation_id": presentation_id,
        "salesPlay": sales_play_list,
        "user_input_id": user_input_id,
    }

    try:
      state = GlobalState()
      state.context = initial_context
      agenda_agent = AgendaAgent(config)
      state = agenda_agent.run(state)

      # Generate GCS URL for outline
      bucket_name = config.get("bucket", "content")
      import datetime

      timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
      if er_number:
        filename_str = f"outline_{er_number}_{timestamp}.json"
      else:
        filename_str = f"outline_no_er_{user_input_id}_{timestamp}.json"
      gcs_url = f"gs://{bucket_name}/{filename_str}"

      # Write raw outline JSON to GCS
      try:
        from pitchgen_utils.gcs_util import write_gcs_file

        write_gcs_file(gcs_url, state.to_json())
        print(
            f"[PitchGenSkills] Successfully uploaded outline to GCS: {gcs_url}"
        )
      except Exception as gcse:
        print(
            f"[PitchGenSkills] Warning: Failed to upload outline to GCS: {gcse}"
        )


      # DB Logging Phase 1 removed

      # Wrap response in expected format
      state_dict = json.loads(state.to_json())
      state_dict["filename"] = gcs_url
      wrapped_response = {
          "Status": "True",
          "data": state_dict,
          "message": "Success",
      }
      return json.dumps(wrapped_response, indent=2)
    except Exception as e:
      return json.dumps({"error": str(e)})

  @staticmethod
  def slide_generator_skill(state_json: str) -> str:
    """Phase 2: Generates the final deck structure (content synthesis & slide mapping)

    based on the provided (and potentially refined) GlobalState.

    Args:
        state_json: Serialized GlobalState JSON string, containing potentially
          modified agendas.

    Returns:
        A serialized GlobalState JSON string with final deck structure.
    """
    state_json_str = str(state_json).strip()
    if state_json_str.startswith("{"):
      try:
        payload = robust_json_loads(state_json_str)
        if (
            "context" not in payload
            and "agendas" not in payload
            and (
                "search_query" in payload
                or "user_inputs" in payload
                or "existing_slide_image_url" in payload
                or "business_context" in payload
            )
        ):
          return dispatch_payload(state_json_str)
      except Exception:
        pass

    print("[PitchGenSkills] Generating final deck from state...")
    config = load_config()

    try:
      state = GlobalState.from_json(state_json_str)
      retrieval_agent = RetrievalAgent(config)
      state = retrieval_agent.run(state)
      creative_orch = CreativeOrchestrator(config)
      final_state = creative_orch.run(state)

      # Generate GCS Filenames & URLs
      bucket_name = config.get("bucket", "content")
      import datetime

      timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
      er_number = final_state.context.get("er_number") or ""

      outputs_filename = f"{er_number}_{timestamp}.json"
      architectural_filename = f"architectural_{er_number}_{timestamp}.json"

      gsurl_outputs = f"gs://{bucket_name}/{outputs_filename}"
      gsurl_architectural = f"gs://{bucket_name}/{architectural_filename}"

      # Write files to GCS
      try:
        from pitchgen_utils.gcs_util import write_gcs_file

        # Upload architectural data (reusable slides suggestions)
        write_gcs_file(
            gsurl_architectural, json.dumps(final_state.reusable_slides or {})
        )

        # Upload outputs data (generated sections)
        outputs_data = {"sections": final_state.final_deck_structure or {}}
        write_gcs_file(gsurl_outputs, json.dumps(outputs_data))
        print(
            "[PitchGenSkills] Successfully uploaded architectural and outputs"
            " to GCS."
        )
      except Exception as gcse:
        print(
            "[PitchGenSkills] Warning: Failed to upload Phase 2 outputs to"
            f" GCS: {gcse}"
        )


      # DB Logging Phase 2 removed

      # Return the expected array format for Apps Script
      wrapped_response = [
          {"architectural_filename": architectural_filename},
          {"outputs_filename": outputs_filename},
          {"agenda": 0},
          {"gsurl_architectural": gsurl_architectural},
          {"gsurl_outputs": gsurl_outputs},
      ]
      return json.dumps(wrapped_response, indent=2)
    except Exception as e:
      return json.dumps({"error": str(e)})

  @staticmethod
  def sidebar_search(
      search_query: str, strict_search: bool = False, user_ldap: str = ""
  ) -> str:
    """Search for reusable slides based on a search query.

    Args:
        search_query: The query string to search for (e.g. 'Gaming industry').
        strict_search: Whether to perform a strict tag-based search.
        user_ldap: User's LDAP/email.
    """
    search_query_str = str(search_query).strip()
    if search_query_str.startswith("{"):
      return dispatch_payload(search_query_str)

    print(f"[PitchGenSkills] Sidebar search for: {search_query}...")
    try:
      import traceback
      from agents.sidebar_agent import sidebar_search as search_impl

      return search_impl(search_query, strict_search, user_ldap)
    except Exception as e:
      import traceback

      return json.dumps({"error": f"{str(e)}\n{traceback.format_exc()}"})

  @staticmethod
  def sidebar_generate(
      slide_content: str,
      slide_title: str = "",
      slide_layout: str = "",
      slide_category: str = "",
      deck_id: str = "",
      slide_id: str = "",
      audience: str = "",
      industry: str = "",
      product: str = "",
      region: str = "GLOBAL",
      action: str = "add_generate",
      er_number: str = "21212",
      user_ldap: str = "",
      presentation_id: str = "",
      slide_image_url: str = "",
  ) -> str:
    """Generate a new slide based on the given instructions."""
    slide_content_str = str(slide_content).strip()
    if slide_content_str.startswith("{"):
      return dispatch_payload(slide_content_str)

    print(f"[PitchGenSkills] Sidebar generate for: {slide_title}...")
    try:
      from agents.sidebar_agent import sidebar_generate as generate_impl

      return generate_impl(
          slide_content=slide_content,
          slide_title=slide_title,
          slide_layout=slide_layout,
          slide_category=slide_category,
          deck_id=deck_id,
          slide_id=slide_id,
          audience=audience,
          industry=industry,
          product=product,
          region=region,
          action=action,
          er_number=er_number,
          user_ldap=user_ldap,
          presentation_id=presentation_id,
          slide_image_url=slide_image_url,
      )
    except Exception as e:
      import traceback

      return json.dumps({"error": f"{str(e)}\n{traceback.format_exc()}"})

  @staticmethod
  def process_json_payload(request_file_url: str) -> str:
    """Translates slide texts based on the provided GCS package file.

    Args:
        request_file_url: GCS path containing the slides translation package.

    Returns:
        A serialized JSON string containing the GCS path of the translated
        response: {"response": "gs://..."}.
    """
    request_file_url_str = str(request_file_url).strip()
    if request_file_url_str.startswith("{"):
      return dispatch_payload(request_file_url_str)

    print(f"[PitchGenSkills] Translating slides payload: {request_file_url}...")
    config = load_config()
    try:
      from workflows.translation_workflow import TranslationWorkflow

      skill = TranslationWorkflow(config)
      result_url = skill.execute(request_file_url)


      # DB Logging Translation removed

      return json.dumps({"response": result_url})
    except Exception as e:
      return json.dumps({"error": str(e)})

  @staticmethod
  def transform_visual(request_file_url: str) -> str:
    """Transforms a slide layout or revises its content based on GCS input package.

    Args:
        request_file_url: GCS path containing the slide transformation request.

    Returns:
        A serialized JSON string containing the GCS path of the transformed
        response: {"response": "gs://..."}.
    """
    request_file_url_str = str(request_file_url).strip()
    if request_file_url_str.startswith("{"):
      return dispatch_payload(request_file_url_str)

    print(f"[PitchGenSkills] Reshuffling slide payload: {request_file_url}...")
    config = load_config()
    try:
      from workflows.reshuffle_workflow import ReshuffleWorkflow

      skill = ReshuffleWorkflow(config)
      result_url = skill.execute(request_file_url)

      # DB Logging Reshuffle removed

      return json.dumps({"response": result_url})
    except Exception as e:
      return json.dumps({"error": str(e)})

  @staticmethod
  def translate_slide_payload(payload_json: str) -> str:
    """Translates a full presentation JSON object via GCS upload and TranslationWorkflow.

    Args:
        payload_json: JSON string containing 'presentationId', 'targetLanguage',
          and the presentation data mapping dict.
    """
    if isinstance(payload_json, dict):
      payload = payload_json
    else:
      payload_json_str = str(payload_json).strip()
      if payload_json_str.startswith("{"):
        return dispatch_payload(payload_json_str, default_action="translate")
      try:
        payload = robust_json_loads(payload_json_str)
      except Exception as e:
        return json.dumps({"error": f"Failed to parse JSON payload: {str(e)}"})

    print("[PitchGenSkills] Translating slide payload via GCS...")
    try:
      res = execute_gcs_translation(payload)
      return json.dumps(res)
    except Exception as e:
      return json.dumps({"error": str(e)})

  @staticmethod
  def transform_slide_payload(payload_json: str) -> str:
    """Transforms a slide's layout or content directly in-memory.

    Args:
        payload_json: JSON string containing 'action', 'toggle', and target
          params (slide_layout, slide_category, output_criteria,
          slide_image_url).
    """
    payload_json_str = str(payload_json).strip()
    if payload_json_str.startswith("{"):
      return dispatch_payload(payload_json_str, default_action="transform")

    print("[PitchGenSkills] Reshuffling/Polishing slide payload in-memory...")
    config = load_config()
    try:
      from agents.slide_engineering_agent import SlideEngineeringAgent

      agent = SlideEngineeringAgent(config)
      payload = json.loads(payload_json)
      payload["action"] = "transform"
      result = agent.run_payload(payload)
      return json.dumps(result)
    except Exception as e:
      return json.dumps({"error": str(e)})

  @staticmethod
  def generate_visual_payload(payload_json: str) -> str:
    """Generates new visuals or transforms existing slide images in-memory.

    Args:
        payload_json: JSON string containing either 'user_inputs' (for
          generation) or 'existing_slide_image_url' (for transformation).
    """
    payload_json_str = str(payload_json).strip()
    if payload_json_str.startswith("{"):
      return dispatch_payload(payload_json_str)

    print("[PitchGenSkills] Generating/Transforming slide visual in-memory...")
    config = load_config()
    try:
      from agents.visual_agent import VisualAgent

      agent = VisualAgent(config)
      payload = json.loads(payload_json)
      result = agent.run_payload(payload)
      return json.dumps(result)
    except Exception as e:
      import traceback

      return json.dumps({"error": f"{str(e)}\n{traceback.format_exc()}"})

  @staticmethod
  def sales_play(request_file_url: str) -> str:
    """Processes Sales Play customized deck copy and customer research content generation.

    Args:
        request_file_url: GCS path containing the sales play request.

    Returns:
        A serialized JSON string containing the GCS path of the final response:
        {"response": "gs://..."}.
    """
    print(
        f"[PitchGenSkills] Processing Sales Play payload: {request_file_url}..."
    )
    config = load_config()
    try:
      from agents.workflows.sales_play_workflow import SalesPlayWorkflow

      skill = SalesPlayWorkflow(config)
      result_url = skill.execute(request_file_url)
      return json.dumps({"response": result_url})
    except Exception as e:
      return json.dumps({"error": str(e)})

  

  @staticmethod
  def debug_list_dir(path: str = ".") -> str:
    """Debug tool to list files in the container.

    Args:
        path: The root path to search.
    """
    try:
      import os
      import sys

      info = {
          "cwd": os.getcwd(),
          "sys_path": sys.path,
          "listdir": os.listdir("."),
      }
      return json.dumps(info)
    except Exception as e:
      return str(e)


# Create the Agent for ADK Web UI
config = load_config()
project_id = config.get("default", "project_name")
region = config.get("default", "region", fallback="us-central1")
model_name = config.get(
    "default", "gemini_model", fallback="gemini-3.1-flash-lite"
)

# Use 'global' location for the model path since gemini-3.5-flash and all other
# listed models in this project are accessible via the 'global' location.
model_region = "global"


def route_payload_before_model(callback_context, llm_request):
  if not llm_request.contents:
    return None
  
  last_content = llm_request.contents[-1]
  if not last_content.parts:
    return None
  
  last_part = last_content.parts[-1]
  if not last_part.text:
    return None
    
  text = last_part.text.strip()
  if text.startswith('"') and text.endswith('"'):
    try:
      import json
      parsed = json.loads(text)
      if isinstance(parsed, str):
        text = parsed.strip()
    except Exception:
      pass

  if not text.startswith("{"):
    return None
    
  try:
    print("[PitchGenSkills] before_model_callback: Intercepting JSON payload...")
    result_str = dispatch_payload(text)
    from google.adk.models.llm_response import LlmResponse
    from google.genai.types import Content, Part
    return LlmResponse(
        content=Content(
            role="model",
            parts=[Part(text=result_str)]
        )
    )
  except Exception as e:
    print(f"[PitchGenSkills] before_model_callback: Error during dispatch: {e}")
    return None


root_agent = Agent(
    name="pitchgen_multiagent",
    before_model_callback=route_payload_before_model,
    model=f"projects/{project_id}/locations/{model_region}/publishers/google/models/{model_name}",
    description=(
        "A powerful agent for automating sales pitch deck blueprints using the"
        " Coordinator-Agent-Skill hierarchy."
    ),
    instruction=(
        "You are the PitchGen ADK 2.0 Orchestrator. Your mission is to assist"
        " users in creating professional sales pitch blueprints.\n\nThis is a"
        " two-phase process for generating new pitch decks:\n1. Phase 1"
        " (Outline Generation): Use the 'create_proposal_outline' tool to"
        " generate the initial outline and agendas. CRITICAL: After Phase 1"
        " completes, you MUST STOP, present the outline/agendas to the user,"
        " and ask them to validate, edit, or approve it. Do NOT call"
        " 'slide_generator_skill' yet!\n2. Phase 2 (Final Deck Generation):"
        " Once the user has reviewed and explicitly approved or modified the"
        " outline, take that outline (represented as the state JSON,"
        " incorporating any edits they provided) and call the"
        " 'slide_generator_skill' tool to generate the final deck"
        " structure.\n\nFor other features:\n- For slide translation, use the"
        " 'process_json_payload' tool (or the direct 'translate_slide_payload'"
        " tool).\n- For slide visual transformation or content revision, use"
        " the 'transform_visual' tool (or the direct 'transform_slide_payload'"
        " tool).\n- For generating or transforming slide images, use"
        " 'generate_visual_payload'.\n- For automated Sales Play assembly and"
        " insights generation, use the 'sales_play' tool.\n- For searching reusable"
        " slides in the sidebar, use 'sidebar_search'.\n- For generating new slides"
        " in the sidebar, use 'sidebar_generate'."
    ),
    tools=[
        PitchGenSkills.create_proposal_outline,
        PitchGenSkills.slide_generator_skill,
        PitchGenSkills.process_json_payload,
        PitchGenSkills.translate_slide_payload,
        PitchGenSkills.transform_visual,
        PitchGenSkills.transform_slide_payload,
        PitchGenSkills.generate_visual_payload,
        PitchGenSkills.sales_play,
        PitchGenSkills.sidebar_search,
        PitchGenSkills.sidebar_generate,
        PitchGenSkills.debug_list_dir,
    ],
)

if __name__ == "__main__":
  # If run directly, it can act as a simple CLI or just print the agent config
  print(f"Agent {root_agent.name} is ready for ADK Web UI.")

from google.adk.apps.app import App

app = App(root_agent=root_agent, name="src")

