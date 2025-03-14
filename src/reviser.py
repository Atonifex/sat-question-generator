import json
import csv
import time
from typing import Dict, List
from openai import OpenAI
from src.config import (OPENAI_API_KEY, REQUEST_DELAY, RESPONSE_FORMAT, SKILL_PROMPTS, OPENAI_MODEL, REASONING_EFFORT, EVALUATION_TOTAL_SCORE_GOOD_TO_USE,
    READING_DIFFICULTY_GUIDELINES, WRITING_DIFFICULTY_GUIDELINES, MATH_DIFFICULTY_GUIDELINES
)
from pathlib import Path
import random

class QuestionReviser:
    def __init__(self, csv_file_path: Path):
        self.client = OpenAI(api_key=OPENAI_API_KEY)
        self.csv_file_path = csv_file_path
        self.columns = ["timestamp", "raw_json", "skill", "difficulty", "question", "choices", "answer", "explanation",
            "Initial Feedback", "P2-Revised JSON", "Revised Question", "Revised Choices", "Revised Answer", "Revised Explanation",
            "Low Level Student Simulation", "High Level Student Simulation", "Question Rating", "Explanation Rating", "Constructive Feedback", "Difficulty Rating", "Total Score", "Final JSON SAT Question"]
        # Define the Structured Output settings for OpenAI's API response
        self.response_format = RESPONSE_FORMAT
        self.skill_prompts = SKILL_PROMPTS
        self.model= OPENAI_MODEL
        self.reasoning_effort = REASONING_EFFORT
        self.reading_difficulty_guidelines = READING_DIFFICULTY_GUIDELINES
        self.writing_difficulty_guidelines = WRITING_DIFFICULTY_GUIDELINES
        self.math_difficulty_guidelines = MATH_DIFFICULTY_GUIDELINES


    def revise_batch(self, questions: List[Dict]) -> List[Dict]:
        revised_questions = []
        for i, question in enumerate(questions):
            #STEP 1: print(f"Revising question {i+1} of {len(questions)}")
            feedback = self.perform_quality_checks(question)
            print(f"Feedback in reviser.py's revise_batch: {feedback}")

            #STEP 2:Apply revisions to the question
            revised_question = self.apply_revisions(question, feedback)
            if revised_question:
                print(f"Revised Question {i+1} of {len(questions)}") #Use this to show teh quetsion itself. {revised_question}
            else:
                revised_question = question
                print("Error: No revisions applied")
            time.sleep(REQUEST_DELAY)  # Rate limiting

            #STEP 3:Rates question 1-10 on internal logic and explanation qualilty, providing suggestions for improvement
            evaluation = self.evaluate_question(revised_question)
            if evaluation:
                print(f"Evaluation Results: {evaluation}")
            time.sleep(REQUEST_DELAY)  # Rate limiting

            # Compute total score and categorize question
            question_rating = evaluation.get("question_rating", 0)
            explanation_rating = evaluation.get("explanation_rating", 0)
            difficulty_rating = evaluation.get("difficulty_appropriateness_rating", 0)

            #STEP 4:Check if evaluation is 17/20 or higher and put into revised_questions; otherwise output to a different directory.
            if isinstance(question_rating, int) and isinstance(explanation_rating, int):
                total_rating = question_rating + explanation_rating + difficulty_rating
                if total_rating >= 28:
                    final_question = revised_question
                    print(f"Yay! Score: {total_rating} - added to revised_questions and csv with only 1st round changes")

                elif total_rating >= EVALUATION_TOTAL_SCORE_GOOD_TO_USE:
                    print(f"Score: {total_rating}. Sending for improved content and formatting.")
                    
                    #STEP 5:FINAL IMPROVE QUESTION CONTENT AND FORMATTING
                    final_question = self.improve_question_content(revised_question, evaluation)
                    time.sleep(REQUEST_DELAY)  # Rate limiting
                    print(f"Final question after improvement: {final_question.get('question')}\n {final_question.get('choices')}")#\n {final_question.get('answer')}\n {final_question.get('explanation')}")
                else:
                    print(f"Fail Score: {total_rating}. Reason: {evaluation.get('constructive_feedback', 'No feedback given.')}")
                    final_question = revised_question #Fall back to OG

                final_question["total_score"] = total_rating
                final_question["constructive_feedback"] = evaluation.get("constructive_feedback", "")
                final_question["difficulty_feedback"] = evaluation.get("difficulty_feedback", "")

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
            filtered_questions = [q for q in data['questions'] if q['skill'] == skill and q['difficulty'] == difficulty] #skill and difficulty
            if len(filtered_questions) < 4:
                filtered_questions = [q for q in data['questions'] if q['skill'] == skill] #skill only - expand the pool

        # Load skill-specific formatting and difficulty guidelines
        skill_guidelines = self.skill_prompts.get(skill)
        if skill in READING_SKILLS:
            difficulty_guidelines = self.reading_difficulty_guidelines.get(difficulty)
        elif skill in WRITING_SKILLS:
            difficulty_guidelines = self.writing_difficulty_guidelines.get(difficulty)
        else: #It's in Math - ****LATER CONSIDER IF I NEED TO BREAK UP MATH INTO SUB-SECTIONS FOR DIFFICUCLTY
            difficulty_guidelines = self.math_difficulty_guidelines.get(difficulty) 

        # Select up to 3 random examples
        examples = random.sample(filtered_questions, min(4, len(filtered_questions)))

        # Format examples for inclusion in the prompt
        examples_text = "\n\n".join(
            f"Question {i+1}. {ex['question']}\nChoices: {ex['choices']}\nAnswer: {ex['answer']}\nExplanation: {ex.get('explanation', 'No explanation provided')}"
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
                     1. Does the question have a clear context, objective, and question? (For example, if the question references 'based on the passage or excerpt or equation' - is there actually a passage, excerpt, or equation in the question? If not, change the question to have an appropriate one.)
                     2. Is there sufficient information given to determine the correct answer?
                     3. Is there exactly one correct answer with 3 plausible but incorrect choices?
                     4. Does the explanation align with the correct answer, and would it be actually educational and insightful to a high school student? If not, what would improve it? Consider SAT tips, strategies, or core knowledge to impart quickly. Generally the first sentence should be succinct in explaining the core reasoning, with the next 1-2 sentences expanding on it or modeling steps in logical thinking or Math. Finally, 1-2 sentences can explain why the incorrect answers are wrong.
                     5. Is the formatting correct? For example, the spacing between paragraphs should be \\n\\n, but there should be no \\n between sentences in a continuous paragraph; confirm that Math expressions use LaTeX with "$" before and after math expressions.
                     6. Does the question align with the {difficulty} difficulty specified in the {difficulty_guidelines}? IF not, change the 'difficulty' in the JSON output to {difficulty}, and adjust complexity of language and reasoning to match. 
                     7. Reference the skill guidelines here: {skill_guidelines}. The question style MUST test the '{skill}' skill; if it doesn't you should adjust the format of the question and answer choices to reflect the directions in the skill guidelines and in the examples provided below.
                    
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

            return feedback
        except Exception as e:
            print(f"Error during quality checks: {e}")
            return {}

    def apply_revisions(self, question: Dict, feedback: Dict) -> Dict:
        """Revise the question based on feedback."""
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-2024-11-20", #can try o1 later for better results.
                #Structured Output JSON formatting:
                response_format=self.response_format,
                messages=[
                    {"role": "system","content": 
                        """You are an expert SAT question writer and reviser. Revise the following question based on the provided feedback"""},
                    {"role": "user", "content": f"""You MUST follow the feedback EXACTLY and revise the question. 
                    Here is the question to revise: {json.dumps(question)}
                    Here is the feedback: {feedback}"""}
                ]
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
                        print("No questions found in apply_revisionresponse, returning original.")
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

        """3/11/2025: Removed these from the response_format, underneath "properties" but could add back in later:
                high_level_student_simulation": {
                    "type": "string",
                    "description": "Simulate solving the question from the role of an advanced high school student at a 1500 out of 1600 SAT score."
                },
                "low_level_student_simulation": {
                    "type": "string",
                    "description": "Simulate solving the question from the role of a very below average ability high school student at a 900 out of 1600 SAT score, who makes common mistakes in grammar, math concepts, and reading comprehension."
                },
                
            Also, if adding in the above, need to add these beneath the "required" section
            "high_level_student_simulation", "low_level_student_simulation", 
                """

        evaluate_question_response_format = {
            "type": "json_schema",
            "json_schema": {
                "name": "sat_questions",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {
                        "question_rating": {
                            "type": "number",
                            "description": "rating from 1-10 evaluating Logical design, clarity, and alignment with SAT standards.",
                        },
                        "explanation_rating": {
                            "type": "number",
                            "description": "Rating from 1-10 for the quality of the explanation.",
                        },
                        "difficulty_appropriateness_rating": {
                            "type": "number",
                            "description": "Rating from 1-10 for the appropriateness of the question to its labeled difficulty.",
                        },
                        "constructive_feedback": {
                            "type": "string",
                            "description": "Explains reasoning for the question_rating and explanation_rating scores, including observations of what is good and bad, and includes suggestions for improving them towards making the question a 10 for both categories.",
                        },
                        "difficulty_feedback": {
                            "type": "string",
                            "description": "Provides specific feedback on how well the question matches its labeled difficulty.",
                        },
                        "total_score": {
                            "type": "number",
                            "description": "The sum of the question_rating, explanation_rating, and difficulty_appropriateness_rating.",
                        }
                    },
                    "required": ["question_rating", "explanation_rating", "difficulty_appropriateness_rating", "constructive_feedback", "difficulty_feedback", "total_score"],
                    "additionalProperties": False  # Prevents unexpected keys in feedback objects
                }
            }
        }

        try:
            #Load up other examples of {skill} and {difficulty} to review - specifically for formatting examples
            with open('all-sat-tests-final.json', 'r', encoding='utf-8') as f:
                
                skill = question.get("skill")
                difficulty = question.get("difficulty")

                data = json.load(f)
                filtered_questions = [q for q in data['questions'] if q['skill'] == skill and q['difficulty'] == difficulty] #skill and difficulty
                # Select up to 3 random examples
                examples = random.sample(filtered_questions, min(4, len(filtered_questions)))
                
                if len(examples) == 3: #plenty of examples in the difficulty
                    examples_combined = "\n\n".join(
                        f"Question {i+1}. {ex['question']}\nChoices: {ex['choices']}\nAnswer: {ex['answer']}\nExplanation: {ex.get('explanation', 'No explanation provided')}"
                        for i, ex in enumerate(examples)
                    )
                    example_text = f"""\n\nFor reference, here are some examples of {skill} questions at {difficulty} difficulties:\n{examples_combined} to compare for formatting, difficulty, and language use."""
                elif len(examples) > 0:
                    filtered_questions = [q for q in data['questions'] if q['skill'] == skill] #skill only - expand the pool
                    examples = random.sample(filtered_questions, min(4, len(filtered_questions)))
                    examples_combined = "\n\n".join(
                        f"Question {i+1}. {ex['question']}\nChoices: {ex['choices']}\nAnswer: {ex['answer']}\nExplanation: {ex.get('explanation', 'No explanation provided')}"
                        for i, ex in enumerate(examples)
                    )
                    example_text = f"""\n\nFor reference, here are some examples of {skill} questions at varying difficulties:\n{examples_combined}"""
                else:
                    example_text = ""

            
            skill_guidelines = self.skill_prompts.get(skill)
            #Load up the difficulty guidelines for the question
            if skill in READING_SKILLS:
                difficulty_guidelines = self.reading_difficulty_guidelines.get(difficulty)
            elif skill in WRITING_SKILLS:
                difficulty_guidelines = self.writing_difficulty_guidelines.get(difficulty)
            else: #It's in Math - ****LATER CONSIDER IF I NEED TO BREAK UP MATH INTO SUB-SECTIONS FOR DIFFICUCLTY
                difficulty_guidelines = self.math_difficulty_guidelines.get(difficulty)
            
            response = self.client.chat.completions.create(
                model=self.model,  # Use the model from config. Previously gpt-4o-2024-11-20
                reasoning_effort=self.reasoning_effort,
                response_format=evaluate_question_response_format,
                messages=[
                    {
                        "role": "developer",  # Use developer for o1/o3 models, but system for gpt-4o...
                        #Removed the student simulations because they were not helpful and made the model more confused.
                        #Previous developer content prompt in case I want to add it back: simulating two students' perspectives (one very high level, and one very low). Then you consider their perspectives, problem solving strategies, sense making, and struggles, and 
                        "content": (
                            """You are an expert SAT question evaluator whose job is to evaluate the generated question based on the below categories, and then to recommend whether the question be published to high school students to practice on our website, or if it should be discarded (if the sum of the ratings is below 20, it will be discarded). If it should be kept but you see opportunities for improvement based on your evaluation, provide specific feedback to improve the SAT question."""
                        ),
                    },
                    {
                        "role": "user", #***Need to make sure the evaluate_question_response_format matches what is asked for here.
                        "content": (
                            f"""First, evaluate the quality of the question and its answer choices and explanation, then give ratings from 1-10 on how good the question is (and whether it should be released publicly to millions of students to use as SAT practice, if so, should it be improved, or should it be discarded). Be objective but very critical because you are the final reviewer. Use the criteria below:\n
                            - **Question Rating (1-10)**: Logical design, clarity, and alignment with SAT standards. Consider whether the amount of struggle by the low level student is applicable for the difficulty (high difficulty should be hard and induce mistakes, but low difficulty shoudl be doable); the high level student should do great on all but the most challenging questions. Be very critical in evaluating if the question actually provides the context it says it does, and whether the question is actually solvable by the student. Propose specific changes if it isn't, or if there's a way to make it better. Finally, reference the skill guidelines here for this evaluation: {skill_guidelines}.Here are example scores:\n
                               - 1-4: Question has critical issues (e.g., multiple correct answers; a excerpt is referenced but not included in the question; the question is not clear or does not logically link with the answer choices; the answer choices are not plausible; the explanation is not helpful; the question doesn't feel like an SAT question).\n
                               - 5-7: Question has a clear objective but minor flaws (e.g., there are inappropriate underlines, line breaks or HTML tags;the question is not aligned with the difficulty level; the answer is way too obvious; the context is not real or is generic (i.e. bad example: "an economist wrote..." vs good example: "Milton Friedman, a famous economist, wrote in his 1970 essay, "The Social Responsibility of Business Is to Increase Its Profits," ...)).\n
                               - 8-9: Question is clear, logically sound, and SAT-aligned but could be improved to be more challenging or to match the proper syntax and formatting (i.e. mistakenly italicizing when text should be underlined, or underlining when no underlining is necessary like in an Inference question).
                               - 10: The question is perfect and is ready to be published to high school students to practice on our website.\n
                            - **Explanation Rating (1-10)**: Insightfulness, conciseness, and clarity in helping the students reflect and learn. 
                            Consider effective strategies that the high level student uses, and consider areas where the low level student is confused or struggles. 
                            Be critical and identify both what is good about the explanation, easy to understand, but also critically evaluate if the explanation is actually applicable to the question and correct answer and if it could be used by the student. 
                            Be specific in what should be changed and why. Example scores:\n
                               - 1-4: Explanation is off-topic or fails to clarify the reasoning.\n
                               - 5-7: Explanation is relevant but lacks depth or includes minor errors.\n
                               - 8-9: Explanation models reasoning, application of relevant core knowledge, and test-taking strategies effectively (10 = excellent).\n
                               - 10: The explanation is perfect and is ready to be published to high school students to practice on our website.\n
                            - **Difficulty Appropriateness Rating (1-10)**: How well does the question match its labeled {difficulty} difficulty? Consider the difficulty guidelines for {difficulty} questions: {difficulty_guidelines}. Also consider the difficulty guidelines here: {skill_guidelines}. Finally, compare the the relative difficulty of this question with the example questions at the end of this prompt.
                               - 1-3: Question is significantly easier or harder than labeled
                               - 4-7: Question is somewhat misaligned with labeled difficulty
                               - 8-10: Question appropriately matches labeled difficulty

                            Add your three ratings together to get the total_score.
                            
                            Last, summarize your thoughts and give specific constructive_feedback with reasoning. Also, explain your reasoning for giving the evaluation scores, consider how the question compares to the examples, and confidently give specific directions to improve the question.

                            For difficulty_feedback, provide specific difficulty feedback explaining why the question does or doesn't match its labeled difficulty, and what changes would make it more appropriate.
                            ***Here is the SAT Question you need to evaluate:{json.dumps(question)}{example_text}"""
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
            difficulty_feedback = evaluation.get("difficulty_feedback", "")
            difficulty_rating = evaluation.get("difficulty_appropriateness_rating", 5)
            
            # Create input payload with emphasis on difficulty correction if needed
            difficulty_instruction = ""
            if difficulty_rating < 7:
                difficulty_instruction = f"""
                This question has been rated {difficulty_rating}/10 for difficulty appropriateness.
                It does not properly match its labeled {question.get('difficulty')} difficulty level.
                
                Specific difficulty feedback: {difficulty_feedback}
                
                When revising this question, prioritize adjusting its difficulty to properly match {question.get('difficulty')} level
                by implementing the specific changes mentioned in the feedback.
                """
            
            response = self.client.chat.completions.create(
                model="gpt-4o-2024-11-20",
                response_format=self.response_format,
                messages=[
                    {
                        "role": "system",  # Use system role for gpt-4o
                        "content": (
                            """You are an expert SAT question reviser specializing in difficulty calibration and quality improvement."""
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            f"""Revise this question based on the provided feedback, with special attention to the formatting suggestions, content changes, and matching the appropriate difficulty level. You MUST follow the feedback and make the changes.
                            
                            \nFeedback: {evaluation_feedback}
                            \nDifficulty Feedback:{difficulty_instruction}
                            \nQuestion: {json.dumps(question)}"""
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
                    "Difficulty Rating": evaluation.get("difficulty_appropriateness_rating", ""),
                    "Total Score": evaluation.get("total_score", ""),
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