import json
import csv
import time
from typing import Dict, List
from openai import OpenAI
from src.config import OPENAI_API_KEY, REQUEST_DELAY, RESPONSE_FORMAT, SKILL_PROMPTS, OPENAI_MODEL, REASONING_EFFORT, DIFFICULTY_GUIDELINES
from pathlib import Path
import random

class QuestionReviser:
    def __init__(self, csv_file_path: Path):
        self.client = OpenAI(api_key=OPENAI_API_KEY)
        self.csv_file_path = csv_file_path
        self.columns = ["timestamp", "raw_json", "skill", "difficulty", "question", "choices", "answer", "explanation",
            "Initial Feedback", "P2-Revised JSON", "Revised Question", "Revised Choices", "Revised Answer", "Revised Explanation",
            "Low Level Student Simulation", "High Level Student Simulation", "Question Rating", "Explanation Rating", "Constructive Feedback", "Final JSON SAT Question"]
        # Define the Structured Output settings for OpenAI's API response
        self.response_format = RESPONSE_FORMAT
        self.skill_prompts = SKILL_PROMPTS
        self.model= OPENAI_MODEL
        self.reasoning_effort = REASONING_EFFORT
        self.difficulty_guidelines = DIFFICULTY_GUIDELINES


    def revise_batch(self, questions: List[Dict]) -> List[Dict]:
        revised_questions = []
        for i, question in enumerate(questions):
            #print(f"Revising question {i+1} of {len(questions)}")
            feedback = self.perform_quality_checks(question)
            print(f"Feedback in reviser.py's revise_batch: {feedback}")

            #Apply revisions to the question
            revised_question = self.apply_revisions(question, feedback)
            if revised_question:
                print(f"Revised Question {i+1} of {len(questions)}") #Use this to show teh quetsion itself. {revised_question}
            else:
                revised_question = question
                print("Error: No revisions applied")
            time.sleep(REQUEST_DELAY)  # Rate limiting

            """# TEMPORARILY BYPASSING EVALUATION AND FORMATTING CHECKS
            # Just add the revised question to the list and save it
            final_question = revised_question
            revised_questions.append(final_question)
            
            # Simplified saving with minimal data
            self.save_revised_question_simple(
                question,
                feedback,
                revised_question
            )# COMMENTED OUT FOR TEMPORARY SIMPLIFICATION
            """
            #Rates question 1-10 on internal logic and explanation qualilty, providing suggestions for improvement
            evaluation = self.evaluate_question(revised_question)
            if evaluation:
                print(f"Evaluation Results: {evaluation}")
            time.sleep(REQUEST_DELAY)  # Rate limiting

            # Compute total score and categorize question
            question_rating = evaluation.get("question_rating", 0)
            explanation_rating = evaluation.get("explanation_rating", 0)

            """#Checks for final formatting with gpt-4o-mini
            syntax_feedback = self.check_formatting_and_syntax(question)
            if syntax_feedback:
                print(f"Syntax Feedback: {syntax_feedback}")
            time.sleep(REQUEST_DELAY)  # Rate limiting
            """

            #Check if evaluation is 17/20 or higher and put into revised_questions; otherwise output to a different directory.
            if isinstance(question_rating, int) and isinstance(explanation_rating, int):
                total_rating = question_rating + explanation_rating
                if total_rating > 18:
                    final_question = revised_question
                    print(f"Yay! Score: {total_rating} - added to revised_questions and csv with only 1st round changes")

                elif total_rating > 12:
                    print(f"Score: {total_rating}. Sending for improved content and formatting.")
                    final_question = self.improve_question_content(revised_question, evaluation)
                    time.sleep(REQUEST_DELAY)  # Rate limiting
                    print(f"Final question after improvement: {final_question.get('question')}")
                else:
                    print(f"Fail Score: {total_rating}. Reason: {evaluation.get('constructive_feedback', 'No feedback given.')}")
                    final_question = revised_question #Fall back to OG

                revised_questions.append(final_question)
                self.save_revised_question(
                    question,
                    feedback,
                    revised_question,
                    evaluation,
                    final_question
                )
            else:
                print("Error: Ratings are not integers. Nothing added to csv.")
                # Still add the question to the list and save minimal data
                final_question = revised_question
                revised_questions.append(final_question)
                self.save_revised_question_simple(
                    question,
                    feedback,
                    revised_question
                )

        return revised_questions

    def perform_quality_checks(self, question: Dict) -> Dict:
        """Evaluate the question and provide feedback."""
        
        # Extract skill and difficulty from the question
        skill = question.get("skill")
        difficulty = question.get("difficulty")
        
        # Now the rest of your code can use these variables
        # Load and filter questions from JSON file
        with open('all-sat-tests-final.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
            #filtered_questions = [q for q in data['questions'] if q['skill'] == skill and q['difficulty'] == difficulty]
            filtered_questions = [q for q in data['questions'] if q['skill'] == skill]
        # Load skill-specific formatting and difficulty guidelines
        skill_guidelines = self.skill_prompts.get(skill)
        difficulty_guidelines = self.difficulty_guidelines.get(difficulty)

        # Select up to 3 random examples
        examples = random.sample(filtered_questions, min(4, len(filtered_questions)))

        # Format examples for inclusion in the prompt
        examples_text = "\n\n".join(
            f"Question {i+1}. {ex['question']}\nChoices: {ex['choices']}\nAnswer: {ex['answer']}\nExplanation: {ex['explanation']}"
            for i, ex in enumerate(examples)
        )
        
        try:
            response = self.client.chat.completions.create(
                model= self.model, #use o3-mini-2025-01-31 with high effort currently. gpt-4o-2024-11-20 was the latest model
                reasoning_effort = "high",
                #No response_format needed here because it's free form text
                messages=[
                    # Previously system prompts weren't followed as closely as user prompts, so consider changing
                    # ALso consider loading up other random examples of {skill} and {difficulty} to review
                    {"role": "developer", "content": 
                        f"""You are an expert SAT question reviewer. Your job is to evaluate potential draft SAT questions based on overall quality, adherence to professional SAT guidelines, and compliance with the user's checklist because the we want to determine if the questions are good enough to be used by high school students on our website to practice the SAT. Be critical and specific, briefly identifying elements that were effective, and aspects, phrases, or syntax that must be fixed."""},
                    
                    {"role": "user", "content": f"""Use the criteria and guiding questions below to determine if the question is a high-quality Digital SAT question for {skill_guidelines} 
                     that logically connects the question, answer, and explanation and can be displayed professionally as a practice question to high school students on an SAT tutoring website because of the proper formatting.
                     If anything does not meet the highest standards, provide specific and detailed feedback on areas for improvement, 
                        succinctly explaining the purpose and justification for the improvement, and including exact wording or syntax changes you suggest 
                        (i.e. 'Math formatting isn't following the skill prompts guidelines, so change "\\[y = 1/2x\\]" to "$y = \\frac{1}{2}x$")
                     If the question satisfies ALL system prompts's checklist and there's nothing to improve, then write 'Previous input perfect; don't change anything'.
                     1. Does the question have a clear context, objective, and question?
                     2. Is there sufficient information given to determine the correct answer?
                     3. Is there exactly one correct answer with 3 plausible but clearly incorrect choices?
                     4. Does the explanation align with the correct answer, and would it be actually educational and insightful to a high school student? If not, what would improve it? Consider SAT tips, strategies, or core knowledge to impart quickly. Generally the first sentence should be succinct in explaining the core reasoning, with the next 1-2 sentences expanding on it or modeling steps in logical thinking or Math. Finally, 1-2 sentences can explain why the incorrect answers are wrong.
                     5. Is the formatting correct? For example, the spacing between paragraphs should be \\n\\n, but there should be no \\n between sentences in a continuous paragraph; confirm that Math expressions use LaTeX with "$" before and after math expressions.
                     6. Does the question align with the {difficulty} difficulty specified in the guidelines? IF not, change the 'difficulty' in the JSON output to {difficulty}, and adjust complexity of language and reasoning to match. Reference the skill guidelines here: {skill_guidelines}. Now also reference the difficulty guidelines here to ensure the perceived difficulty of the question is indeed {difficulty}:{difficulty_guidelines}
                    
                    For reference, here are a few example {skill} questions at varying difficulties:
                    {examples_text}
                    
                    ***Here is the SAT Question you need to evaluate***:
                    """ + json.dumps(question)}
                    #Option to add additional user prompts after json.dumps(question)
                ]
            )
            #print("OpenAI's response message.content:", response.choices[0].message.content)

            #Extract the feedback from the response
            feedback = response.choices[0].message.content
            print(f"Feedback: {feedback}")

            return feedback
        except Exception as e:
            print(f"Error during quality checks: {e}")
            return {}

    def apply_revisions(self, question: Dict, feedback: Dict) -> Dict:
        """Revise the question based on feedback."""
        try:
            #If previous AI recommended no change "Previous input perfect; don't change anything.", return original question instead of wasing AI power
            #if "Previous input perfect; don't change anything" in feedback:
            #    print("Question returned as original")
           #    return question  # Return the original question as a dictionary, not a list

            response = self.client.chat.completions.create(
                model="gpt-4o-2024-11-20", #can try o1 later for better results.
                #Structured Output JSON formatting:
                response_format=self.response_format,
                messages=[
                    {"role": "system","content": 
                        """You are an expert SAT question writer and reviser. Revise the following question based on the provided feedback"""},
                    {"role": "user", "content": """Follow the feedback to revise the question. """ + json.dumps({"feedback": feedback,"question": question})}
                ]
                #If the feedback is 'Previous input perfect; don't change anything', then the output should equal the input.
            )
            response_data = json.loads(response.choices[0].message.content)
            #{questions: [{question: "...", choices: ["...", "...", "..."], answer: "...", explanation: "..."}]}
            questions = response_data.get("questions", [])
            print(f"revised_question is: {questions}")
            
            # Extract the first question from the list
            if questions and len(questions) > 0:
                revised_question = questions[0]  # Get the first dictionary from the list
                if isinstance(revised_question, list): #handles if a list is returned.
                    if len(revised_question) > 0:
                        return revised_question[0]  # Return the first item if it's a list
                    else:
                        return question  # Return original if empty list
                else:
                    return revised_question
            else:
                print("No questions found in response, returning original")
                return question
            
        except Exception as e:
            print(f"Error during revision: {e}")
            return question  # Return original question on error

    def evaluate_question(self, question: Dict) -> Dict:
        """Evaluate the question using simulated student perspectives and structured output."""
        evaluate_question_response_format = {
            "type": "json_schema",
            "json_schema": {
                "name": "sat_questions",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {
                        "high_level_student_simulation": {
                            "type": "string",
                            "description": "Simulate solving the question from the role of an advanced high school student at a 1500 out of 1600 SAT score."
                        },
                        "low_level_student_simulation": {
                            "type": "string",
                            "description": "Simulate solving the question from the role of a very below average ability high school student at a 900 out of 1600 SAT score, who makes common mistakes in grammar, math concepts, and reading comprehension."
                        },
                        "question_rating": {
                            "type": "number",
                            "description": "rating from 1-10 evaluating Logical design, clarity, and alignment with SAT standards.",
                        },
                        "explanation_rating": {
                            "type": "number",
                            "description": "Rating from 1-10 for the quality of the explanation.",
                        },
                        "constructive_feedback": {
                            "type": "string",
                            "description": "Explains reasoning for the question_rating and explanation_rating scores, including observations of what is good and bad, and includes suggestions for improving them towards making the question a 10 for both categories.",
                        }
                    },
                    "required": ["high_level_student_simulation", "low_level_student_simulation", "question_rating", "explanation_rating", "constructive_feedback"],
                    "additionalProperties": False  # Prevents unexpected keys in feedback objects
                }
            }
        }

        try:
            response = self.client.chat.completions.create(
                model=self.model,  # Use the model from config. Previously gpt-4o-2024-11-20
                reasoning_effort=self.reasoning_effort,
                response_format=evaluate_question_response_format,
                messages=[
                    {
                        "role": "developer",  # Use developer for o1/o3 models, but system for gpt-4o...
                        "content": (
                            """You are an expert SAT question evaluator simulating two students' perspectives (one very high level, and one very low). Then you consider their perspectives, problem solving strategies, sense making, and struggles, and rate the questions based on the below categories, then ultimately provide feedback to finalize revisions of the SAT question."""
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            f"""First, simulate solving the question from the perspective of two students' perspectives, showing the students' thoughts, observations, problem solving steps, strategies employed, possible mistakes made, as they answer the questions step by step. """
                            """1) A high-performing student aiming for 1550 out of 1600 who excels on Easy/Medium/Hard questions but struggles a little on very challenging questions. """
                            """2) A very below average student aiming for 900 out of 1600 who makes frequent mistakes and errors in grammar, math concepts, and reading comprehension."""
                            """Second, consider the students' sense making and problem solving, and assess the question rating and explanation rating, being very critical because you are the final reviewer before this question is released publicly to millions of students. Use the criteria below:\n"""
                            """- **Question Rating (1-10)**: Logical design, clarity, and alignment with SAT standards. Consider whether the amount of struggle by the low level student is applicable for the difficulty (high difficulty should be hard and induce mistakes, but low difficulty shoudl be doable); the high level student should do great on all but the most challenging questions. Be very critical in evaluating if the question actually provides the context it says it does, and whether the question is actually solvable by the student. Propose specific changes if it isn't, or if there's a way to make it better. Example scores:\n"""
                            """   - 1-4: Question has critical issues (e.g., multiple correct answers, unclear phrasing).\n"""
                            """   - 5-7: Question has a clear objective but minor flaws (e.g., slightly ambiguous wording, minor alignment issues).\n"""
                            """   - 8-9: Question is clear, logically sound, and SAT-aligned but could be improved.
                                  - 10: The question is perfect and is ready to be published to high school students to practice on our website.\n"""
                            """- **Explanation Rating (1-10)**: Insightfulness, conciseness, and clarity in helping the students reflect and learn. Considser effective strategies that the high level student uses, and consider areas where the low level student is confused or struggles. Be critical and identify both what is good about the explanation, easy to understand, but also critically evaluatae if the explanation is actually applicable to the question and correct answer and if it could be used by the student. Be specific in what should be changed and why. Example scores:\n"""
                            """   - 1-4: Explanation is off-topic or fails to clarify the reasoning.\n"""
                            """   - 5-7: Explanation is relevant but lacks depth or includes minor errors.\n"""
                            """   - 8-9: Explanation models reasoning, application of relevant core knowledge, and test-taking strategies effectively (10 = excellent).\n"""
                            """   - 10: The explanation is perfect and is ready to be published to high school students to practice on our website.\n"""
                            """Last, summarize your thoughts and give specific constructive feedback, explaining reasoning for giving the question_rating and explanation_rating scores and includes suggestions for improving them..
                            
                            \nQuestion to evaluate: {json.dumps(question)}"""
                        ),
                    },
                ],
            )
            response_data = json.loads(response.choices[0].message.content)
            return response_data  # Includes "question_rating", "explanation_rating", and "constructive_feedback"
        except Exception as e:
            print(f"Error during question evaluation: {e}")
            return {}


    def improve_question_content(self, question: Dict, evaluation: Dict) -> Dict:
        """Refine the question based on evaluation feedback."""
        try:
            # Get evaluation feedback
            evaluation_feedback = evaluation.get("constructive_feedback", "")
            
            # Create input payload for the OpenAI revision process
            response = self.client.chat.completions.create(
                model="gpt-4o-2024-11-20",  # Use gpt-4o as requested
                response_format=self.response_format,
                messages=[
                    {
                        "role": "system",  # Use system role for gpt-4o
                        "content": (
                            """You are an expert SAT question reviser and are the last step before this question is publicly released to high school students to practice on our website - 
                            so make sure it's perfect. Use the provided feedback to refine the question, including referencing the students' perspectives to double check if the explanation is clear and helpful - if not, please adjust the explanation.
                            Ensure the revised question meets all quality criteria, aligns with SAT standards, and is formatted correctly.
                            """
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            "Revise the question based on this feedback:"
                            f"\nFeedback: {evaluation_feedback}"
                            f"\nQuestion: {json.dumps(question)}"
                        ),
                    },
                ],
            )

            # Parse the API response
            response_data = json.loads(response.choices[0].message.content)
            revised_and_evaluated_question = response_data.get("questions", [])

            # Return the revised question
            if revised_and_evaluated_question and len(revised_and_evaluated_question) > 0:
                print("Successfully improved question in final stage!")
                return revised_and_evaluated_question[0]  # Return the first item as a dictionary
            else:
                print("No revisions returned; retaining original question.")
                return question

        except Exception as e:
            print(f"Error during question improvement: {e}")
            return question


    
    
    def save_revised_question(self, question, feedback, revised_question: Dict, evaluation: Dict, final_question: Dict):
        """Save the revised question to the CSV file."""
        try:
            with open(self.csv_file_path, 'a', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=self.columns)
                
                #"revised_question" is a List containing 1 dictionary with keys: question, choices, answer, explanation
                #In the future if I batch to two at a time, this could change to multiple questions easily
                #OLD and Non-functional: for revised_question in revised_question:
                #This should be unnecessary because I only do questions one at a time (no need to do multiple in a "batch") because revise_batch already 
                #enumerates over all questions in the batch that are passed to it. 

                row = {
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "raw_json": json.dumps(question, ensure_ascii=False),  # Full JSON
                    "skill": question.get("skill", ""),
                    "difficulty": question.get("difficulty", ""),
                    "question": question.get("question", ""),
                    "choices": "\n".join(question.get("choices", [])),  # Convert list to string
                    "answer": question.get("answer", ""),
                    "explanation": question.get("explanation", ""),
                    "Initial Feedback": feedback,
                    "P2-Revised JSON": json.dumps(revised_question, ensure_ascii=False),
                    "Revised Question": revised_question.get("question", ""),
                    "Revised Choices": "\n".join(revised_question.get("choices", [])),
                    "Revised Answer": revised_question.get("answer", ""),
                    "Revised Explanation": revised_question.get("explanation", ""),
                    "Low Level Student Simulation": evaluation.get("low_level_student_simulation",""),
                    "High Level Student Simulation": evaluation.get("high_level_student_simulation", ""),
                    "Question Rating": evaluation.get("question_rating", ""),
                    "Explanation Rating": evaluation.get("explanation_rating", ""),
                    "Constructive Feedback": evaluation.get("constructive_feedback", ""),
                    "Final JSON SAT Question": json.dumps(final_question, ensure_ascii=False)
                }
                writer.writerow(row)
        except Exception as e:
            print(f"Error saving revised question: {e}")

    # Add a simplified version of save_revised_question that only saves essential data
    def save_revised_question_simple(self, question, feedback, revised_question: Dict):
        """Save the revised question to the CSV file with minimal data."""
        try:
            with open(self.csv_file_path, 'a', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=self.columns)
                
                # Add this type check to handle both list and dictionary cases
                if isinstance(revised_question, list) and len(revised_question) > 0:
                    revised_question_dict = revised_question[0]
                    print("Warning: revised_question was a list, extracting first item")
                else:
                    revised_question_dict = revised_question
                
                row = {
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "raw_json": json.dumps(question, ensure_ascii=False),  # Full JSON
                    "skill": question.get("skill", ""),
                    "difficulty": question.get("difficulty", ""),
                    "question": question.get("question", ""),
                    "choices": "\n".join(question.get("choices", [])),  # Convert list to string
                    "answer": question.get("answer", ""),
                    "explanation": question.get("explanation", ""),
                    "Initial Feedback": feedback,
                    "P2-Revised JSON": json.dumps(revised_question_dict, ensure_ascii=False),
                    "Revised Question": revised_question_dict.get("question", ""),
                    "Revised Choices": "\n".join(revised_question_dict.get("choices", [])),
                    "Revised Answer": revised_question_dict.get("answer", ""),
                    "Revised Explanation": revised_question_dict.get("explanation", ""),
                    # Leave evaluation fields empty
                    "Low Level Student Simulation": "",
                    "High Level Student Simulation": "",
                    "Question Rating": "",
                    "Explanation Rating": "",
                    "Constructive Feedback": "",
                    "Final JSON SAT Question": json.dumps(revised_question_dict, ensure_ascii=False)
                }
                writer.writerow(row)
        except Exception as e:
            print(f"Error saving revised question: {e}")



    #As of 3/7/2025, this is not used because the higher level models do a good enough job at this already.
    def check_formatting_and_syntax(self, question: Dict) -> str:
        """Use a lightweight model to check for formatting and syntax errors."""
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            """You are an expert SAT question formatter and syntax checker. Identify any issues in the following question and suggest corrections. """
                            """Check for:\n"""
                            """1. Missing "$" around math expressions.\n"""
                            """2. Incorrect LaTeX formatting (e.g., missing double backslashes).\n"""
                            """3. Improper use of line breaks and spacing.\n"""
                            """4. Redundant JSON keys (e.g., 'Choices:' or 'Answer:' embedded in the question field).\n"""
                            """5. Missing HTML for tables or graphs referenced in the question.\n"""
                            """Provide specific recommendations for each issue. Example: 'In the "question", '$\frac{1}{5}' should have two backslashes after the $ but before the 'frac', and it also needs a closing '$' after the {5}. Here's the correct version: '$\\frac{1}{5}$'.
                            
                            If all formatting is good, just output this: 'Previous input perfect; don't change anything'"""
                        ),
                    },
                    {
                        "role": "user",
                        "content": json.dumps(question),
                    },
                ],
            )
            return response.choices[0].message.content  # Free-form recommendations
        except Exception as e:
            print(f"Error during formatting/syntax check: {e}")
            return "Error during formatting/syntax check."