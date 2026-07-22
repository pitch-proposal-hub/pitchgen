import sys
from google.cloud import discoveryengine_v1 as discoveryengine

def list_datastores():
    try:
        client = discoveryengine.DataStoreServiceClient()
        project_id = os.environ.get("GCP_PROJECT_ID", "<YOUR_GCP_PROJECT_ID>")
        parent = f"projects/{project_id}/locations/global/collections/default_collection"
        print(f"Listing datastores in {parent}...")
        response = client.list_data_stores(parent=parent)
        for ds in response:
            print(f"Name: {ds.name}")
            print(f"Display Name: {ds.display_name}")
            print("-" * 40)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == '__main__':
    # googleinit removed for external build
    list_datastores()
