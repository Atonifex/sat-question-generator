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
    Save the revised questions to formatted JSON files, separating by quality score.
    
    Args:
        revised_questions: List of question dictionaries
        
    Returns:
        Path to the created/updated JSON file
    """
    # Create a timestamp for the run date (used only for new files)
    timestamp = datetime.now().strftime("%Y%m%d")
    
    # Use a consistent filename that doesn't change between runs
    good_filename = f"SAT_questions_{timestamp}.json"
    bad_filename = "bad_sat_examples.json"
    
    good_file_path = Path(OUTPUT_DIR) / good_filename
    bad_file_path = Path(OUTPUT_DIR) / bad_filename
    
    # Separate questions by score
    good_questions = []
    bad_questions = []
    
    for question in revised_questions:
        # Check if the question has a total_score field
        if "total_score" in question:
            total_score = question["total_score"]
        else:
            # If not, try to calculate it from individual ratings
            total_score = 0
            if "question_rating" in question:
                total_score += question.get("question_rating", 0)
            if "explanation_rating" in question:
                total_score += question.get("explanation_rating", 0)
            if "difficulty_appropriateness_rating" in question:
                total_score += question.get("difficulty_appropriateness_rating", 0)
        
        # Categorize based on score
        if total_score >= 21: #22 or 23 seem to be solid questions, but worth ongoing manual evaluation
            good_questions.append(question)
        else:
            bad_questions.append(question)
    
    # Process good questions
    good_file_result = None
    if good_questions:
        good_file_result = _save_questions_to_file(good_questions, good_file_path, "good")
    
    # Process bad questions
    bad_file_result = None
    if bad_questions:
        bad_file_result = _save_questions_to_file(bad_questions, bad_file_path, "bad")
    
    # Return the path to the good questions file, or the bad questions file if no good questions
    return good_file_result or bad_file_result or "No files created"

def _save_questions_to_file(questions: List[Dict], file_path: Path, quality_label: str) -> str:
    """Helper function to save questions to a file."""
    if file_path.exists():
        # Read existing data
        with open(file_path, 'r', encoding='utf-8') as f:
            try:
                existing_data = json.load(f)
                # Append new questions to existing ones
                existing_data["questions"].extend(questions)
                output_data = existing_data
                action = "Updated"
            except json.JSONDecodeError:
                # If the file exists but is corrupted, create new data
                output_data = {"questions": questions}
                action = "Created new"
    else:
        # Create new data structure
        output_data = {"questions": questions}
        action = "Created"
    
    # Write to file with proper indentation
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
    
    print(f"{action} {quality_label} questions file with {len(questions)} new questions at {file_path} (total: {len(output_data['questions'])})")
    return str(file_path)
    