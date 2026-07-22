import sys
import vertexai


def list_engines():
    try:
        project_id = os.environ.get("GCP_PROJECT_ID", "<YOUR_GCP_PROJECT_ID>")
        location = os.environ.get("GCP_LOCATION", "us-central1")
        client = vertexai.Client(project=project_id, location=location)
        engines = client.agent_engines.list()
        engines_list = list(engines)
        print(f"Found {len(engines_list)} reasoning engines via GenAI Client:")
        for engine in engines_list:
            res = engine.api_resource
            print(f"ID: {res.name.split('/')[-1]}")
            print(f"Display Name: {res.display_name}")
            print(f"Resource Name: {res.name}")
            print("-" * 40)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == '__main__':
    # googleinit removed for external build
    list_engines()
