import sys
import os

from src.new_content_gen import gen_text

def generate_slide_content(agendas, url_list):
    """
    Generates slide content for each agenda item using the existing PitchGen-model logic.
    """
    task_list = []
    for i, agenda in enumerate(agendas):
        key = agenda.get('key')
        if key is not None:
            task_num = int(key) * 10 + 1
        else:
            task_num = (i + 1) * 10 + 1
        task_title = f"{task_num}: {agenda['title']}"
        task_desc = f"{task_title} (Topics: {', '.join(agenda['parts'])})"
        task_list.append([task_desc, 1])
    
    formatted_content, final_source_urls = gen_text(task_list, url_list)
    return formatted_content, final_source_urls

