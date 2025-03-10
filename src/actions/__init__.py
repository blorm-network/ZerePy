import os
import importlib
from pathlib import Path

def import_all_actions():
    current_dir = Path(__file__).parent
    action_files = [
        f for f in os.listdir(current_dir)
        if f.endswith('_actions.py') and not f.startswith('__')
    ]
    
    for action_file in action_files:
        module_name = action_file[:-3]  
        full_module_path = f"src.actions.{module_name}"
        try:
            importlib.import_module(full_module_path)
        except Exception as e:
            print(f"Failed to import {full_module_path}: {e}")

import_all_actions()