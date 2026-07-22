import sys
import os

try:
except ImportError:
  print("[run_adk] Warning: googleinit not available.")
except Exception as e:
  print(f"[run_adk] Warning: googleinit failed: {e}")

# Add the google/cloud/aiplatform path to sys.path so that 'import vertexai' works.

from google.adk.cli.cli_tools_click import main

if __name__ == '__main__':
  # Add the directory containing agent.py to sys.path
  # This is crucial so that ADK can import our agent.
  current_dir = os.path.dirname(os.path.abspath(__file__))
  sys.path.insert(0, current_dir)
  
  # We can also print some debug info
  print(f"Starting ADK CLI from {current_dir}")
  print(f"sys.path: {sys.path}")


  
  main()

