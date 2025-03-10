# generator.py
"""
Simple SAT question generator using OpenAI's API with structured outputs.
Phase 1: Generate basic questions and save to CSV.
"""
import json
import csv
from datetime import datetime
import time
from typing import Dict, List
from openai import OpenAI
from src.config import OPENAI_API_KEY, OUTPUT_DIR, VALID_SKILLS, VALID_DIFFICULTIES, DEFAULT_NUM_QUESTIONS
from pathlib import Path
import random

class QuestionGenerator:
    def __init__(self):
        self.client = OpenAI(api_key=OPENAI_API_KEY)
        self.output_dir = Path(OUTPUT_DIR)
        self.columns = ["timestamp", "raw_json", "skill", "difficulty", "question", "choices", "answer", "explanation"]
        self._initialize_session()
        
        # Define the expected structure for the API response
        self.response_format = {
            "type": "json_schema",
            "json_schema": {
                "name": "sat_questions",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {
                        "questions": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "skill": {
                                        "type": "string",
                                        "enum": VALID_SKILLS,
                                        "description": "The specific skill being tested"
                                    },
                                    "difficulty": {
                                        "type": "string",
                                        "enum": VALID_DIFFICULTIES,
                                        "description": "Difficulty level of the question"
                                    },
                                    "question": {
                                        "type": "string",
                                        "description": "The question text with proper spacing and LaTeX formatting"
                                    },
                                    "choices": {
                                        "type": "array",
                                        "items": {
                                            "type": "string"
                                        },
                                        "description": "Answer choices (A-D for multiple choice, or numerical value for free response)"
                                    },
                                    "answer": {
                                        "type": "string",
                                        #"enum": ["A", "B", "C", "D"], #if free response, this is a number or fraction, so no enum
                                        "description": "Correct answer (A-D for multiple choice, or numerical value for free response)"
                                    },
                                    "explanation": {
                                        "type": "string",
                                        "description": "Step-by-step explanation with proper spacing and LaTeX formatting"
                                    }
                                },
                                "required": [
                                    "skill",
                                    "difficulty",
                                    "question",
                                    "choices",
                                    "answer",
                                    "explanation"
                                ],
                                "additionalProperties": False
                            }
                        }
                    },
                    "required": ["questions"],
                    "additionalProperties": False
                }
            }
        }

    def _initialize_session(self):
        """Initialize a new CSV session."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.session_file = self.output_dir / f"questions_{timestamp}.csv"
        
        # Create file and write header
        with open(self.session_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=self.columns)
            writer.writeheader()
        print(f"Initialized new session: {self.session_file}")
    
    def generate_batch(self, skill: str, difficulty: str, num_questions: int = 3) -> list:
        """Generate multiple questions with rate limiting."""
        questions = []
        
        for i in range(num_questions):
            print(f"Generating question {i+1} of {num_questions}")
            question = self.generate_question(skill, difficulty)
            if question:
                questions.append(question)
            time.sleep(1)  # Rate limiting
            
        return questions
    
    #Consider rewriting generate_question to create 2-3 questions at a time, saving input tokens cost
    def generate_question(self, skill: str, difficulty: str) -> Dict:
        """Generate a single SAT question using OpenAI."""
        try:
            print(f"Generating {difficulty} {skill} question...")

            # Load and filter questions from JSON file
            with open('all-sat-tests-final.json', 'r', encoding='utf-8') as f:
                data = json.load(f)
                filtered_questions = [q for q in data['questions'] if q['skill'] == skill]

            # Select up to 5 random examples
            examples = random.sample(filtered_questions, min(6, len(filtered_questions)))

            # Format examples for inclusion in the prompt
            examples_text = "\n\n".join(
                f"Question {i+1}. {ex['question']}\nChoices: {ex['choices']}\nAnswer: {ex['answer']}\nExplanation: {ex['explanation']}"
                for i, ex in enumerate(examples)
            )
            print(f"Examples included in prompt: {examples_text}")

            response = self.client.chat.completions.create(
                model="gpt-4o-2024-11-20",
                response_format=self.response_format,
                messages=[
                    {"role": "system", 
                    "content": 
                        """You are an expert Digital SAT question writer. Create an original, high-quality question 
                        that follows proper formatting:
                        - Use LaTeX for all mathematical expressions with two backslashes for the expressions when inside "$". Example: $\\\\frac{...}{...}$ or $\\\\sqrt{...}$
                        - Use \n\n for paragraph breaks
                        - Use proper unicode for symbols
                        - Follow the exact JSON schema provided"""},
                    {"role": "user", 
                    "content": #{difficulty} difficulty - removed this to see how difficulty may vary
                    #Even with teh new #2, 3/4 Supporting Claims questions didn't have a real question
                        f"""Generate a {skill} question. Return in the specified JSON format. Follow this checklist to ensure the question is complete:
                        1. Start with a clear question statement that requires a choice from the provided options.
                        2. Provide one correct answer choice and three plausible but incorrect answer choices.
                        3. Include an explanation that clearly and concisely articulates the reasoning an expert SAT test taker would use.
                        4. Follow the formatting rules: LaTeX with "$...$" for math expressions, \n\n for paragraph breaks, unicode, "_..._" for underlining, *...* for italics, **...** for bold.
                        5. Ensure the difficulty of the question is appropriate based on the complexity and challenge compared to the examples below.
                        Use these examples as inspiration, but your content should be original and distinct: \n{examples_text}"""
                        }
                ]
            )
            
            # Parse the response, doubly ensure it's valid JSON
            response_data = json.loads(response.choices[0].message.content)
            questions = response_data.get("questions", [])

            if not questions:
                print("No questions found in response")
                return None
            
            question_data = questions[0]
            preview = (question_data.get('question', '') or '')[:30]
            print(f"Generated question: {preview}")
            self.save_to_csv(question_data)
            
            return question_data
            
        except Exception as e:
            print(f"Error generating question: {e}")
            return None

    def save_to_csv(self, question: Dict):
        """Save single question to CSV file."""
        try: #a is append mode, w is write mode. 
            with open(self.session_file, 'a', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=self.columns)

                row = {
                    "timestamp": datetime.now().isoformat(),
                    "raw_json": json.dumps(question, ensure_ascii=False),  # Full JSON
                    "skill": question.get("skill", ""),
                    "difficulty": question.get("difficulty", ""),
                    "question": question.get("question", ""),
                    "choices": "\n".join(question.get("choices", [])),  # Convert list to string
                    "answer": question.get("answer", ""),
                    "explanation": question.get("explanation", "")
                    }
                writer.writerow(row)
        except Exception as e:
            print(f"Error saving to CSV: {e}")

"""Generate a test batch of questions."""
"""
def main():
    generator = QuestionGenerator()
    questions = []
    
    # Generate DEFAULT_NUM_QUESTIONS test questions
    for _ in range(DEFAULT_NUM_QUESTIONS):
        question = generator.generate_question(
            skill="Supporting Claims",
            difficulty="Medium"
        )
        if question:
            questions.append(question)
        time.sleep(1)  # Simple rate limiting
        """
    
    # Save to CSV - done immediately in generate_question 1 question at a time
    #if questions:
    #    generator.save_to_csv(questions)


"""
Previous prompts used:
Generate a {skill} question. Return in the specified JSON format. Follow this checklist to ensure the question is complete:
1. Is there pertinent information given which will direct the student to a clear and appropriate Digital SAT style question?
2. Is there one correct answer choice which logically follows from the question and three plausible but incorrect answer choices?
3. Does your explanation clearly and concisely articulate the reasoning that an expert SAT test taker would think?
4. Did you follow the formatting rules? (LaTeX with "$...$" for math expressions, \n\n for paragraph breaks, unicode, "_..._" for underlining, *...* for italics, **...** for bold)
5. Is the difficulty of the question based on the complexity of the question and how challenging it is compared to the other question examples below and their respective difficulties?
Follow the format and style of the below example questions, but your content should be original and distinct: \n{examples_text}"""
