import sys
import os
import json
import re
from google import genai
from google.genai import types

from src.template_sorting import get_placeholders_json
from src.configuration import configuration

def select_layout(text_content):
    """
    Uses Gemini to classify the content and select an appropriate template layout.
    """
    config = configuration()
    project_id = config['default']['PROJECT_NAME']
    model_id = config['default']['GEMINI_MODEL']
    
    client = genai.Client(
        vertexai=True,
        project=project_id,
        location=config['default']['region'],
    )
    
    available_layouts = [
        "Context", "Case Study", "Charts", "Circle Charts", "Next Steps", 
        "Timeline", "GC_AI_Title and content", "GC_AI_Divider", "GC_AI_Agenda",
        "CS_Title and content", "CS_Divider", "CS_Agenda", "Customer References",
        "GTM_GTM Layout", "GC_AI_Content slides"
    ]
    
    prompt = f"""
    Analyze the following slide content and select the most appropriate template layout from the list provided.
    
    Slide Content:
    {text_content}
    
    Available Layouts:
    {", ".join(available_layouts)}
    
    Return ONLY the name of the selected layout. Do not include any other text.
    """
    
    response = client.models.generate_content(
        model=model_id,
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0,
        )
    )
    
    selected = response.text.strip()
    for layout in available_layouts:
        if layout.lower() in selected.lower():
            return layout
            
    return "Context"

def process_slides_with_templates(formatted_content, agendas):
    """
    Iterates through formatted content, selects templates, and generates placeholder JSONs.
    """
    tasks = re.split(r'-----Task \d+ Completed successfully-----', formatted_content)
    tasks = [t.strip() for t in tasks if t.strip()]
    
    results = {}
    
    for i, (task_content, agenda) in enumerate(zip(tasks, agendas)):
        if agenda.get('cust_ref') == 'true':
            layout = "Customer References"
        else:
            layout = select_layout(task_content)
        
        key = agenda.get('key')
        if key is not None:
            agenda_num = str(key)
            task_num = int(key) * 10 + 1
        else:
            agenda_num = str(i + 1)
            task_num = (i + 1) * 10 + 1
            
        wrapped_task = f"-----Task {task_num}-----\n{task_content}"
        
        try:
            placeholders_output = get_placeholders_json(wrapped_task, layout)
            
            if 'agendas' in placeholders_output and agenda_num in placeholders_output['agendas']:
                slides = placeholders_output['agendas'][agenda_num]['slides']
            else:
                first_agenda_key = list(placeholders_output.get('agendas', {}).keys())[0]
                slides = placeholders_output['agendas'][first_agenda_key]['slides']
            
            results[agenda_num] = {
                "title": agenda['title'],
                "slides": slides
            }

        except Exception as e:
            print(f"Error processing placeholders for agenda {i}: {e}")
            results[str(i)] = {
                "title": agenda['title'],
                "slides": {},
                "error": str(e)
            }
            
    total_templates = 41 
    return results, total_templates
