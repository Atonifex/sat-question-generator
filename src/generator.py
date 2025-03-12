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
from src.config import OPENAI_API_KEY, DEFAULT_NUM_QUESTIONS, RESPONSE_FORMAT, SKILL_PROMPTS, REASONING_EFFORT, REQUEST_DELAY, OPENAI_MODEL, DIFFICULTY_GUIDELINES, OVERUSED_TOPICS
from pathlib import Path
import random

class QuestionGenerator:
    def __init__(self, csv_file_path: Path):
        self.client = OpenAI(api_key=OPENAI_API_KEY)
        self.csv_file_path = csv_file_path
        self.columns = ["timestamp", "raw_json", "skill", "difficulty", "question", "choices", "answer", "explanation"]
        #self._initialize_session() #commented out below too so csv is written by both generator and reviser
        
        # Define the Structured Output settings for OpenAI's API response
        self.response_format = RESPONSE_FORMAT
        self.skill_prompts = SKILL_PROMPTS
        self.reasoning_effort = REASONING_EFFORT
        #self.max_completion_tokens = MAX_COMPLETION_TOKENS
        self.model = OPENAI_MODEL
        self.difficulty_guidelines = DIFFICULTY_GUIDELINES
        self.overused_topics = OVERUSED_TOPICS

    
    def generate_batch(self, skill: str, difficulty: str, num_questions: int = 3, topic: str = None) -> list:
        """Generate multiple questions with rate limiting."""
        questions = []
        
        for i in range(num_questions):
            #print(f"Generating question {i+1} of {num_questions}")
            question = self.generate_question(skill, difficulty, topic)
            if question:
                questions.append(question)
            time.sleep(REQUEST_DELAY)  # Rate limiting
            
        return questions
    
    def generate_question(self, skill: str, difficulty: str, topic: str = None) -> Dict:
        """Generate a single SAT question using OpenAI."""
        try:
            #print(f"Generating {difficulty} {skill} question...")

            # Load and filter questions from JSON file
            with open('all-sat-tests-final.json', 'r', encoding='utf-8') as f:
                data = json.load(f)
                filtered_questions = [q for q in data['questions'] if q['skill'] == skill and q['difficulty'] == difficulty] #skill and difficulty
                print(f"Added {len(filtered_questions)} filtered questions to generate question prompt.")
                if len(filtered_questions) < 4:
                    filtered_questions = [q for q in data['questions'] if q['skill'] == skill] #skill only - expand the pool
                    print(f"Not enough questions for {difficulty} {skill}. Expanded to all skills and got{len(filtered_questions)} questions.")

            # Select up to 5 random examples
            examples = random.sample(filtered_questions, min(6, len(filtered_questions)))

            # Format examples for inclusion in the prompt
            examples_text = "\n\n".join(
                f"Question {i+1}. {ex['question']}\nChoices: {ex['choices']}\nAnswer: {ex['answer']}\nExplanation: {ex['explanation']}"
                for i, ex in enumerate(examples)
            )
                

            #Load skill-specific formatting and difficulty guidelines
            skill_guidelines = self.skill_prompts.get(skill)
            difficulty_guidelines = self.difficulty_guidelines.get(difficulty)

            
            #print(f"Examples included in prompt: {examples_text}")

            # Dynamic structured output with enforced difficulty - CONSIDER THIS at 5:55 pm on 3/7 if manually changing didn't work below. This is slightly more hardcore.
            #dynamic_response_format = json.loads(json.dumps(self.response_format).replace('"{requested_difficulty}"', f'"{difficulty}"'))
            
            response = self.client.chat.completions.create(
                model = 'o1-2024-12-17', #self.model (o1/03)
                response_format = self.response_format,
                #response_format = dynamic_response_format, #Use this if I usue dynamic_response_format above.

                reasoning_effort = "medium",
                messages=[
                    {"role": "developer", #use "developer" when using o3 and o1 models and "system" when using gpt-4o-2024-11-20
                    "content": 
                        """You are an expert Digital SAT question writer. Create an original, high-quality question based on the topic provided in the prompt that follows proper formatting specified:
                        - Provide one correct answer choice and three plausible but incorrect answer choices. The correct answer choice should equally likely to be A, B, C, or D; you have a bad tendency of making B and C always the correct answers, so make A and D also be correct sometimes.
                        - Use \n\n for paragraph breaks with single backslashes before the n (DO NOT use HTML elements like <br> or <p> tags)
                        - Follow the formatting rules: LaTeX with "$...$" for math expressions, unicode, "_underlined text_" for underlining, *italicized text* for italics, **bold text** for bold.
                        - Use unicode for symbols (i.e. \\u2022 for bullet points, \\u2019 for apostrophe, etc.)
                        - Follow the exact JSON schema provided (i.e. ONLY WRITE questions in "question", and do NOT write the answer choices or explanation here!)"""},
                    {"role": "user", 
                    "content": 
                        """Generate a Digital SAT question testing the ***{skill}*** skill at ***{difficulty}*** difficulty in the specified JSON format.
                        1. Write the question and answer choices based on this topic: {topic}.     
                        2. There must always be a clear question afterwards, separated with a double line break from the previous text (\\n\\n).
                        3. Include an explanation that clearly articulates reasoning an expert SAT test-taker would use, but write in a helpful, very simple and straightforward language that a high school student could use to understand how to solve the question, learn underlying concepts, and apply SAT test-taking strategies.
                        4. Don't use unnecessary underlining, italics, or bold.
                        5. Use the {skill} skill guidelines to understand how to write a question that tests the {skill} skill: {skill_guidelines}. 
                        5. Use the {difficulty} difficulty guidelines to write a question that is at the {difficulty} difficulty: {difficulty_guidelines}. 
                        6. ***The output JSON's 'difficulty' value MUST BE 'difficulty': '{difficulty}'***
                        7. Finally, extrapolate patterns from the SAT example questions below while creatively varying the sentence and paragraph structure, language, and style so that the question is distinct from the examples provided but still academic and SAT-like: \n{examples_text}"""
                    }
                        #*********************IN THE FUTURE, try without #9 (providing any questions) because reasoning models are supposed to be better at this****************
                        # --> I tried without it, but it was obsessed with writing about Harriet Tubman, literally 50% of questions were about her despite no examples provided about harriet tubman. So weird.
                        #3/11/2025 at 11:29 pm removed "Include diverse real-world context in questions to create a valid question testing the {skill} skill."
                ]
            )
            
            # Parse the response, doubly ensure it's valid JSON
            response_data = json.loads(response.choices[0].message.content)
            questions = response_data.get("questions", [])

            if not questions:
                print("No questions found in response")
                return None
            
            question_data = questions[0]
            
            # Force the correct difficulty level
            if question_data.get('difficulty') != difficulty:
                print(f"Warning: Generated question had difficulty '{question_data.get('difficulty')}' instead of requested '{difficulty}'. Correcting.")
                question_data['difficulty'] = difficulty
            
            preview = (question_data.get('question', '') or '')[:30]
            #print(f"Generated question: {preview}")
            
            return question_data
            
        except Exception as e:
            print(f"Error generating question: {e}")
            return None

    def save_to_csv(self, question: Dict):
        """Save single question to CSV file."""
        try: #a is append mode, w is write mode. 
            with open(self.csv_file_path, 'a', newline='', encoding='utf-8') as f:
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

"""
Debugging the JSON sent to OpenAI:
# Add this before your API call
            print("API Request Payload:", json.dumps({
                "model": self.model,
                "messages": [
                    {"role": "developer", #use "developer" when using o3 and o1 models and "system" when using gpt-4o-2024-11-20
                    "content": 
                        You are an expert Digital SAT question writer. Create an original, high-quality question that follows proper formatting specified and is similar in form to the examples provided:
                        - The correct answer choice should be be random between A-D, meaning 25 percent D, 25 percent B, 25 percent C, and 25 percent A.
                        - Use \n\n for breaks between paragraphswith single backslashes before the n
                        - Use unicode for symbols (i.e. \\2022 for bullet points, etc.)
                        - Follow the exact JSON schema provided (i.e. ONLY WRITE questions in "question")},
                    {"role": "user", 
                    "content": #{difficulty} difficulty - removed this to see how difficulty may vary
                    #Even with teh new #2, 3/4 Supporting Claims questions didn't have a real question

                        Generate a {difficulty} {skill} Digital SAT question. Return in the specified JSON format. Follow this checklist to ensure the question is complete:
                        1. Ensure all questions include informational context and end with a clear question. often with a double line break below (\\n\\n).
                        2. Provide one correct answer choice and three plausible but incorrect answer choices. {difficulty_guidelines}
                        3. Include an explanation that clearly articulates reasoning an expert SAT test-taker would use, but write in very simple and straightforward language that a high school student could use to understand how to solve the question and learn underlying concepts.
                        4. Follow the formatting rules: LaTeX with "$...$" for math expressions, USE \n\n for paragraph breaks (DO NOT USE <br>), unicode, use "_" before and after a pharse or sentence to underline like in "_underlined text_", *italicized text* for italics, **bold text** for bold.
                        5. Ensure questions vary in tone, level of abstraction, and real-world context. Incorporate diverse contexts such as science, history, social studies, or practical decision-making contexts.
                        6. Design the question and answer choices to align with the {difficulty} description in these skill guidelines: {skill_guidelines}. 
                        7. Extrapolate patterns from the SAT example questions below but introduce creative variations in phrasing, challenge, and style so that the question is distinct from the examples provided: \n{examples_text}
                        }
                        #*********************IN THE FUTURE, try without #7 (providing any questions) because reasoning models are supposed to be better at this****************
                ],
                "response_format": self.response_format
            }, indent=2))

#These are the old prompts
                        fGenerate a {difficulty} {skill} Digital SAT question. Return in the specified JSON format. Follow this checklist to ensure the question is complete:
                        1. All questions have some informational context and end in a question, many with a separate line break.
                        2. Provide one correct answer choice and three plausible but incorrect answer choices.
                        3. Include an explanation that clearly and concisely articulates the reasoning an expert SAT test taker would use.
                        4. Follow the formatting rules: LaTeX with "$...$" for math expressions, \n\n for paragraph breaks, unicode, "_underlined text_" for underlining, *italicized text* for italics, **bold text** for bold.
                        5. Design the question and answer choices to match the description of {difficulty} difficulty in the skill-specific formatting guidelines and examples afterwards: {skill_guidelines}
                        Here are examples of these formatting guidelines in action. Use the below examples as inspiration for question structure, but your content should be original and distinct, using different context and information: \n{examples_text}

Previous prompts used:
Generate a {skill} question. Return in the specified JSON format. Follow this checklist to ensure the question is complete:
1. Is there pertinent information given which will direct the student to a clear and appropriate Digital SAT style question?
2. Is there one correct answer choice which logically follows from the question and three plausible but incorrect answer choices?
3. Does your explanation clearly and concisely articulate the reasoning that an expert SAT test taker would think?
4. Did you follow the formatting rules? (LaTeX with "$...$" for math expressions, \n\n for paragraph breaks, unicode, "_..._" for underlining, *...* for italics, **...** for bold)
5. Is the difficulty of the question based on the complexity of the question and how challenging it is compared to the other question examples below and their respective difficulties?
Follow the format and style of the below example questions, but your content should be original and distinct: \n{examples_text}


previous difficulty guidelines:
Medium and Hard difficulty questions should have more tempting incorrect answers that may be partially right. Here are some examples of reasons for incorrect answers:
                           - Misleading question statement trap that tempts students to answer too quickly without reading the full question 
                           - Partially correct questions have some aspects that are true (i.e. describing the function of a sentence correctly, but providing the wrong reasoning) 
                           - Wrong unit or format - double check your Math units because you might do the right Math but be solving for the number of inches instead of feet.  
                           - Over-complication trap - language shouldn't be needlessly complicated, and some questions can be straightforward (especially earlier in the test)

"""
