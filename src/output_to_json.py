"""
Utility to output revised SAT questions to a formatted JSON file.
"""
import json
import os
from typing import List, Dict
from pathlib import Path
from datetime import datetime
from src.config import OUTPUT_DIR

def output_to_json(revised_questions: List[Dict]) -> str:
    """
    Save the revised questions to a formatted JSON file, appending to an existing file if it exists.
    
    Args:
        revised_questions: List of question dictionaries
        
    Returns:
        Path to the created/updated JSON file
    """
    # Create a timestamp for the run date (used only for new files)
    timestamp = datetime.now().strftime("%Y%m%d")
    
    # Use a consistent filename that doesn't change between runs
    filename = f"SAT_questions_{timestamp}.json"
    file_path = Path(OUTPUT_DIR) / filename
    
    # Check if the file already exists
    if file_path.exists():
        # Read existing data
        with open(file_path, 'r', encoding='utf-8') as f:
            try:
                existing_data = json.load(f)
                # Append new questions to existing ones
                existing_data["questions"].extend(revised_questions)
                output_data = existing_data
                action = "Updated"
            except json.JSONDecodeError:
                # If the file exists but is corrupted, create new data
                output_data = {"questions": revised_questions}
                action = "Created new"
    else:
        # Create new data structure
        output_data = {"questions": revised_questions}
        action = "Created"
    
    # Write to file with proper indentation
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
    
    print(f"{action} file with {len(revised_questions)} new questions at {file_path} (total: {len(output_data['questions'])})")
    return str(file_path)
    