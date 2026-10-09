import sys
import os
import json

# Add 'src' and parent directories to sys.path so that internal imports resolve
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
src_dir = os.path.join(parent_dir, "src")

sys.path.insert(0, src_dir)
sys.path.insert(0, parent_dir)

from config_loader import load_config
from agents.workflows.template_mapper_workflow import TemplateMapperWorkflow

def main():
    config = load_config()
    mapping = TemplateMapperWorkflow(config)
    
    # 1. Title Slide
    deck_title = "Google Cloud AI: Transform Starbucks Supply Chain"
    print(f"\n--- Mapping Title slide for title: '{deck_title}' ---")
    try:
        result = mapping.execute(deck_title, "", layout="GC_AI_Title")
        print(json.dumps(result, indent=2))
    except Exception as e:
        print(f"Error: {e}")

    # 2. Agenda Slide
    agenda_content = """* Business Objectives & Cloud Migration
* Supply Chain Optimization via AI
* Predictive Forecasting & Inventory Management
* Next Steps & Implementation Roadmap"""
    print(f"\n--- Mapping Agenda slide for: --- \n{agenda_content}")
    try:
        result = mapping.execute("Agenda", agenda_content, layout="GC_AI_Agenda")
        print(json.dumps(result, indent=2))
    except Exception as e:
        print(f"Error: {e}")

    # 3. Divider Slide
    section_title = "Supply Chain Optimization via AI"
    print(f"\n--- Mapping Divider slide for section: '{section_title}' ---")
    try:
        result = mapping.execute("Section 2", section_title, layout="GC_AI_Divider")
        print(json.dumps(result, indent=2))
    except Exception as e:
        print(f"Error: {e}")

if __name__ == '__main__':
    main()
