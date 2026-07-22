import json
import random
from agents.base_agent import BaseAgent
from agents.workflows.content_synthesis_workflow import ContentSynthesisWorkflow
from agents.workflows.layout_transformer_workflow import LayoutTransformerWorkflow
from agents.workflows.reusable_slide_customizer_workflow import ReusableSlideCustomizerWorkflow
from agents.workflows.slide_assembly_workflow import SlideAssemblyWorkflow
from agents.workflows.template_mapper_workflow import TemplateMapperWorkflow
from agents.workflows.text_transformer_workflow import TextTransformerWorkflow
from agents.workflows.translation_engine_workflow import TranslationEngineWorkflow


def get_final_content(item, place_holders, agendas, reusable_slides, sources):
    """
    Generate the final presentation content by merging placeholders, agendas, and reusable slides.

    Args:
        place_holders (dict): The placeholders for slide content.
        agendas (dict): The structured agendas.
        reusable_slides (dict): The reusable slide suggestions.
        customer_name (str): The name of the customer.

    Returns:
        dict: The final structured content for the presentation.
    """
    noAgendas = len(agendas.keys())

    # Locate mapping.json dynamically to be robust to different working directories
    import os
    mapping_path = 'config/mapping.json'
    if not os.path.exists(mapping_path):
        import inspect
        caller_file = inspect.getfile(inspect.currentframe())
        caller_dir = os.path.dirname(os.path.abspath(caller_file))
        possible_paths = [
            os.path.join(caller_dir, 'config/mapping.json'),
            os.path.join(caller_dir, '../config/mapping.json'),
            os.path.join(caller_dir, '../../config/mapping.json'),
            os.path.join(caller_dir, 'src/config/mapping.json'),
            os.path.join(caller_dir, '../src/config/mapping.json'),
            os.path.join(caller_dir, '../../src/config/mapping.json'),
            'src/config/mapping.json',
            'config/mapping.json'
        ]
        for path in possible_paths:
            if os.path.exists(path):
                mapping_path = path
                break

    with open(mapping_path,'r') as f:
        mappings = json.loads(f.read())

    try:
        title_slide_id = mappings['title'][str(random.randint(1, 3))]
    except KeyError:
        title_keys = [k for k in mappings['title'].keys() if k != 'deckId']
        title_slide_id = mappings['title'][random.choice(title_keys)]

    title_slide = {
        "temp_url": (
          f"https://docs.google.com/presentation/d/"
          f"{mappings['title']['deckId']}/edit#slide=id.{title_slide_id}"
        ),
        "placeholders": {"title": item.title}
      }

    if noAgendas < 4:
        agenda_slide_id = random.choice(mappings['agenda']['4'])
    elif noAgendas > 10:
        agenda_slide_id = random.choice(mappings['agenda']['10'])
    else:
        try:
            agenda_slide_id = random.choice(mappings['agenda'][str(noAgendas)])
        except KeyError:
            agenda_keys = [k for k in mappings['agenda'].keys() if k != 'deckId']
            agenda_slide_id = random.choice(mappings['agenda'][random.choice(agenda_keys)])

    ph_dict = {}
    for key in agendas.keys():
        ph_dict["agenda"+key] = agendas[key]['title']
    agenda_slide = {
        "temp_url": f"https://docs.google.com/presentation/d/{mappings['agenda']['deckId']}/edit#slide=id.{agenda_slide_id}",
        "placeholders": ph_dict
      }

    try:
        divider_slide_ids = mappings['divider'][str(random.randint(1, 4))]
    except KeyError:
        divider_keys = [k for k in mappings['divider'].keys() if k != 'deckId']
        divider_slide_ids = mappings['divider'][random.choice(divider_keys)]

    divider_slides = {}
    for key in agendas.keys():
        ind = (int(key) - 1) % 4
        divider_slides[key] = {
        "temp_url": (
          f"https://docs.google.com/presentation/d/"
          f"{mappings['divider']['deckId']}/edit#slide=id."
          f"{divider_slide_ids[ind]}"
        ),
        "placeholders": {
            "num": "{:02d}".format(int(key)),
            "title": agendas[key]['title']
            },
        "sources": sources[key] if key in sources.keys() else []
        }

    try:
        thank_slide_id = mappings['thank'][str(random.randint(1, 6))]
    except KeyError:
        thank_keys = [k for k in mappings['thank'].keys() if k != 'deckId']
        thank_slide_id = mappings['thank'][random.choice(thank_keys)]

    thank_slide = {
        "temp_url": (
          f"https://docs.google.com/presentation/d/"
          f"{mappings['thank']['deckId']}/edit#slide=id."
          f"{thank_slide_id}"
        ),
      }

    sections = {}
    sections["title"] = {"slides": {"1": title_slide}}
    sections["agenda"] = {"slides": {"1": agenda_slide}}

    for i in range(noAgendas):
        agenda_key = str(i + 1)
        sections[f"divider_{agenda_key}"] = {"slides": {"1": divider_slides[agenda_key]}}
        if agenda_key in place_holders:
            sections[agenda_key] = place_holders[agenda_key]
        else:
            sections[agenda_key] = {"slides": {}}

    sections["thank_you"] = {"slides": {"1": thank_slide}}

    finalcontent_struct = {"sections": sections}

    return finalcontent_struct



class SlideEngineeringAgent(BaseAgent):

  def __init__(self, config):
    super().__init__(
        "SlideEngineeringAgent",
        "Responsible for synthesizing, transforming and assembling slides.",
    )
    self.config = config

    # Equip agent with all 7 skills (3 original for monolithic orchestrator + 4 remote ones for direct payload service)
    self.add_skill("synthesis", ContentSynthesisWorkflow(config))
    self.add_skill("mapping", TemplateMapperWorkflow(config))
    self.add_skill("customizer", ReusableSlideCustomizerWorkflow(config))
    self.add_skill("layout_transformer", LayoutTransformerWorkflow(config))
    self.add_skill("text_transformer", TextTransformerWorkflow(config))
    self.add_skill("translation_engine", TranslationEngineWorkflow(config))
    self.add_skill("slide_assembly", SlideAssemblyWorkflow(config))

  def transform_slide(
      self, slide_layout, slide_category, output_criteria, slide_image_url=None, slide_id=None
  ):
    """Transforms slide content based on layout, category, output criteria, and slide image."""
    content_str = self.skills["layout_transformer"].execute(
        slide_layout=slide_layout,
        slide_category=slide_category,
        output_criteria=output_criteria,
        slide_image_url=slide_image_url,
        slide_id=slide_id,
    )
    return self.skills["slide_assembly"].execute(
        content=content_str, status="success"
    )

  def translate_presentation(self, presentation_data, target_language="German"):
    """Recursively translates all text entries in the presentation structure."""

    def translate_func(val):
      return self.skills["translation_engine"].execute(
          val, target_language=target_language
      )

    return self._recursive_transform_text(presentation_data, translate_func)

  def _recursive_transform_text(self, item, transform_func):
    if isinstance(item, dict):
      new_dict = {}
      for k, v in item.items():
        if k.lower() == "text" and isinstance(v, str):
          new_dict[k] = transform_func(v)
        else:
          new_dict[k] = self._recursive_transform_text(v, transform_func)
      return new_dict
    elif isinstance(item, list):
      return [self._recursive_transform_text(x, transform_func) for x in item]
    else:
      return item

  def run(self, global_state):
    print(f"[{self.name}] Starting creative synthesis...")

    # 1. Synthesize new content for gaps
    new_content = self.skills["synthesis"].execute(global_state)
    global_state.generated_content = new_content

    # 2. Map to templates (with visual deduplication!)
    mapped_slides = {}
    used_slide_ids = []
    import re

    if not hasattr(global_state, "reusable_slides") or global_state.reusable_slides is None:
      global_state.reusable_slides = {}

    # --- Generate Title Slide ---
    deck_title = global_state.outline.get("title") if global_state.outline else None
    if not deck_title:
      deck_title = global_state.context.get("customer_name", "Presentation")
    
    print(f"[{self.name}] Generating Title Slide for: '{deck_title}'...")
    try:
      title_result = self.skills["mapping"].execute(deck_title, "", layout="GC_AI_Title")
      selected_id = title_result.get("slide_id")
      if selected_id:
        used_slide_ids.append(selected_id)
      mapped_slides["title"] = {"slides": {"1": title_result}}
      global_state.reusable_slides["title"] = {"suggestions": []}
    except Exception as e:
      print(f"[{self.name}] Error generating Title slide: {e}")

    # --- Generate Agenda Slide ---
    if global_state.agendas:
      agenda_items = [agenda.get("title", "") for agenda in global_state.agendas.values()]
      agenda_content = "\n".join([f"* {item}" for item in agenda_items])
      print(f"[{self.name}] Generating Agenda Slide...")
      try:
        agenda_result = self.skills["mapping"].execute("Agenda", agenda_content, layout="GC_AI_Agenda")
        selected_id = agenda_result.get("slide_id")
        if selected_id:
          used_slide_ids.append(selected_id)
        mapped_slides["agenda"] = {"slides": {"1": agenda_result}}
        global_state.reusable_slides["agenda"] = {"suggestions": []}
      except Exception as e:
        print(f"[{self.name}] Error generating Agenda slide: {e}")

    # --- Generate Divider Slides for all sections ---
    if global_state.agendas:
      for key, agenda in global_state.agendas.items():
        section_title = agenda.get("title", "")
        print(f"[{self.name}] Generating Divider Slide for Section {key}: '{section_title}'...")
        try:
          divider_result = self.skills["mapping"].execute(f"Section {key}", section_title, layout="GC_AI_Divider")
          selected_id = divider_result.get("slide_id")
          if selected_id:
            used_slide_ids.append(selected_id)
          mapped_slides[f"divider_{key}"] = {"slides": {"1": divider_result}}
          global_state.reusable_slides[f"divider_{key}"] = {"suggestions": []}
        except Exception as e:
          print(f"[{self.name}] Error generating Divider slide for Section {key}: {e}")

    # Process content sections (gaps)
    for key, content_str in new_content.items():
      # Parse multiple slides from the generated content string
      pattern = r"Slide\s*\d*\s*Title:\s*(.*?)\s*Slide\s*\d*\s*Content:\s*(.*?)(?=Slide\s*\d*\s*Title:|$)"
      matches = re.findall(pattern, content_str, re.DOTALL)

      slides_dict = {}
      slide_idx = 1

      # If parsing fails to find any slides, fallback to mapping the whole content as one slide
      if not matches:
        print(
            f"[{self.name}] Warning: Failed to parse slides from content for key"
            f" {key}. Falling back to single slide mapping."
        )
        print(f"[{self.name}] Raw content was:\n=== RAW ===\n{content_str}\n=== END RAW ===")
        result = self.skills["mapping"].execute(
            "Generated Slide", content_str, used_slide_ids=used_slide_ids
        )
        selected_id = result.get("slide_id")
        if selected_id:
          used_slide_ids.append(selected_id)
        slides_dict[str(slide_idx)] = result
      else:
        for title, content in matches:
          title = title.strip()
          content = content.strip()
          print(f"[{self.name}] Mapping parsed slide: '{title}'...")
          result = self.skills["mapping"].execute(
              title, content, used_slide_ids=used_slide_ids
          )
          selected_id = result.get("slide_id")
          if selected_id:
            used_slide_ids.append(selected_id)
          slides_dict[str(slide_idx)] = result
          slide_idx += 1

      mapped_slides[key] = {"slides": slides_dict}

    # Integrate get_final_content to build the final presentation structure
    class ObjectView(object):
      def __init__(self, d):
        self.__dict__ = d

    title_str = "Google Cloud Pitch Presentation"
    if hasattr(global_state, 'outline') and global_state.outline and isinstance(global_state.outline, dict):
      title_str = global_state.outline.get("title", title_str)
    elif hasattr(global_state, 'context') and global_state.context and isinstance(global_state.context, dict):
      if global_state.context.get("customer_name"):
        title_str = f"Google Cloud Proposal for {global_state.context.get('customer_name')}"
      elif global_state.context.get("business_context"):
        title_str = global_state.context.get("business_context")
    
    item_obj = ObjectView({"title": title_str})
    agendas_dict = global_state.agendas or {}
    reusable_slides_dict = getattr(global_state, "reusable_slides", {}) or {}
    sources_dict = getattr(global_state, "sources", {}) or {}

    finalcontent_struct = get_final_content(
        item=item_obj,
        place_holders=mapped_slides,
        agendas=agendas_dict,
        reusable_slides=reusable_slides_dict,
        sources=sources_dict
    )
    global_state.final_deck_structure = finalcontent_struct.get("sections", {})

    # 3. Dynamically customize retrieved Reusable Slides based on account research & active GTM skills!

    if (
        hasattr(global_state, "reusable_slides")
        and global_state.reusable_slides
    ):
      print(
          f"[{self.name}] Starting dynamic customization of retrieved Reusable"
          " Slides..."
      )
      customizer = self.skills["customizer"]
      tasks = []
      for key, slide_group in global_state.reusable_slides.items():
        suggestions = slide_group.get("suggestions", [])
        for sug in suggestions:
          if sug.get('_source_datastore_key') == 'cust_ref':
            print(
                f"[{self.name}] Skipping customization for Customer Reference"
                f" slide: '{sug.get('name')}'"
            )
            continue
          tasks.append(sug)
          
      if tasks:
        from concurrent.futures import ThreadPoolExecutor
        def customize_task(sug):
          try:
            customized_data = customizer.execute(sug, global_state.context)
            sug.update(customized_data)
          except Exception as ex:
            print(f"[{self.name}] Error customizing slide task: {ex}")
            
        max_workers = min(len(tasks), 10)
        print(f"[{self.name}] Customizing {len(tasks)} slides in parallel using {max_workers} threads...")
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
          list(executor.map(customize_task, tasks))

    print(f"[{self.name}] Creative synthesis completed.")
    return global_state
  def run_payload(self, input_data):
    """Direct payload processing for layout reshuffling, text polishing and translation.

    Matches the remote SlideEngineeringAgent routing interface.
    """
    if "search_query" in input_data:
      from Sidebar_search_generator.agent import sidebar_search as search_impl
      import json
      try:
        res = search_impl(
            search_query=input_data.get("search_query"),
            strict_search=input_data.get("strict_search", False),
            user_ldap=input_data.get("user_ldap", ""),
        )
        return json.loads(res)
      except Exception as e:
        return {"error": str(e)}

    action = input_data.get("action")
    if action == "transform":
      toggle_val = input_data.get("toggle")

      # User requested layout reshuffle if toggle is False
      if toggle_val is False or str(toggle_val).lower() == "false":
        return self.transform_slide(
            slide_layout=input_data.get("slide_layout"),
            slide_category=input_data.get("slide_category"),
            output_criteria=input_data.get("output_criteria"),
            slide_image_url=input_data.get("slide_image_url"),
            slide_id=input_data.get("slide_id") or input_data.get("slideId"),
        )
      else:
        # Text Transformation / Polishing (toggle is True)
        presentation_id = input_data.get("presentation_id", "")
        slide_id = input_data.get("slideId", "")
        output_criteria = input_data.get(
            "output_criteria", "Improve clarity and professional tone"
        )

        data_list = input_data.get("data", [])
        new_data_list = []
        for item in data_list:
          new_item = dict(item)
          if "text" in item:
            original_text = item["text"]
            transformed_text = self.skills["text_transformer"].execute(
                original_text, criteria=output_criteria
            )
            new_item["text"] = transformed_text
          new_data_list.append(new_item)

        output_payload = dict(input_data)
        output_payload["data"] = new_data_list
        output_payload["json_filename"] = (
            f"reshuffle_true/{presentation_id}_{slide_id}.json"
        )

        import json

        content_json_str = json.dumps(output_payload, indent=2)
        return self.skills["slide_assembly"].execute(
            content=content_json_str, status="success"
        )

    elif action == "translate":
      target_lang = input_data.get("targetLanguage", "German")
      pres_id = input_data.get("presentationId")

      # Extract presentation dict matching presentation_id
      pres_data = input_data.get(pres_id) if pres_id else None

      if target_lang and pres_data is not None:
        transformed_data = self.translate_presentation(pres_data, target_lang)
      else:
        transformed_data = pres_data

      # Return the structured result
      output_data = dict(input_data)
      if pres_id and pres_data is not None:
        output_data[pres_id] = transformed_data

      return {"status": "success", "data": output_data}

    return {"error": f"Unknown action: {action}"}
