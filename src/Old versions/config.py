# src/config.py
"""Configuration settings and constants for the SAT question generator."""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# API Configuration
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
OPENAI_MODEL = "gpt-4o-2024-11-20", #If this isn't excellent, try gpt-4o-2024-08-06

# File paths
BASE_DIR = Path(__file__).parent.parent
INPUT_FILE = BASE_DIR / 'all-sat-tests-final.json'
OUTPUT_DIR = BASE_DIR / 'output'

# Ensure output directory exists
OUTPUT_DIR.mkdir(exist_ok=True)

# Question Generation Settings
DEFAULT_NUM_QUESTIONS = 4
VALID_DIFFICULTIES = ["Easy", "Medium", "Hard"]
VALID_SKILLS = [
    'Function of Sentence', 'Inferences', 'Main Idea', 'Pronouns and Modifiers', 'Punctuation', 'Referencing Data', 'Supporting Claims', "Synthesizing Notes", 'Tenses', 'Transition Words', 'Two Passages', 'Word Choice',
    'Absolute Value', 'Algebra', 'Circles', 'Exponential Equations', 'Exponential Word Problems', 'Geometry', 'Interpreting Graphs', 'Linear Equations', 'Linear Word Problems', 'Inequality Word Problems', 'Percent', 'Polynomial Expressions', 'Probability', 'Quadratic Equations', 'Statistics', 'Systems of Equations', 'Trigonometry', 'Unit Conversions'
]

# Rate Limiting
REQUEST_DELAY = 1  # seconds between requests
MAX_RETRIES = 3