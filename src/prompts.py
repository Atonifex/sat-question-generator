from langchain.prompts import ChatPromptTemplate
from langchain.prompts.chat import SystemMessagePromptTemplate, HumanMessagePromptTemplate

# Base prompt for initial question generation
QUESTION_TEMPLATE = """
You are an expert Digital SAT question writer. Generate a high-quality SAT question that follows these requirements:

1. The question should be clear, engaging, and appropriate for high school students
2. The question must assess the following skill: {skill}
3. The question should match this difficulty level: {difficulty}
4. Adhere strictly to the following JSON format:
   {{
       "skill": "{skill}",
       "difficulty": "{difficulty}",
       "question": "...",
       "choices": ["", "", "", ""],
       "answer": "",
       "explanation": ""
   }}

Example questions of this type:
{examples}

**Important**: 
- Do not add any extra comments or text outside the JSON format.
- Only generate the question; leave choices, answer, and explanation blank for now.
- If the question cannot be generated, return an empty JSON object: {{}}
"""

# Prompt for generating answer choices and explanation
ANSWERS_TEMPLATE = """
For this SAT question: {question}, try to solve it yourself first to validate if it makes sense. If it doesn't, modify the question so it is logical and you can generate a correct answer and concise explanation for why that answer is correct.

Generate:
1. Four answer choices labeled A, B, C, and D
2. Mark the correct answer
3. Provide a clear explanation

Requirements:
- Make incorrect choices plausible but clearly wrong
- Ensure exactly one correct answer
- Write the explanation in clear, student-friendly language
- Follow proper formatting ("$" before and after math expressions and use LaTeX. Example: $y = \\frac{4}{3}$. IF anything should be underlined, add a "_" before and after; use "*" for italics)
"""

# Prompt for validation and quality check
VALIDATION_TEMPLATE = """
Review and improve this SAT question:
{full_question}

Tasks:
1. Ensure the question strictly adheres to this JSON format:
   {{
       "skill": "...",
       "difficulty": "...",
       "question": "...",
       "choices": ["...", "...", "...", "..."],
       "answer": "...",
       "explanation": "...",
       "ratings": {{
           "clarity": ...,
           "plausibility": ...,
           "explanation_quality": ...,
           "formatting": ...
       }}
   }}
2. Fix any missing fields or formatting issues:
   - Check math expressions have "$" before and after
   - Verify proper use of "_" for underlining and "*" for italics
   - Ensure double newlines "\n\n" for spacing
3. Verify that:
   - `"choices"` include four plausible options (one correct and three incorrect).
   - `"answer"` aligns logically with the `"question"` and `"choices"`.
   - `"explanation"` provides a concise, logical explanation of the answer.
   4. Rate from 1-10:
   - Question clarity
   - Answer choice plausibility
   - Explanation quality
   - Overall formatting

Return both the improved question and your ratings. Only return the final question as a JSON object.
"""

# Create prompt templates
question_prompt = ChatPromptTemplate.from_messages([
    SystemMessagePromptTemplate.from_template(
        """You are a Digital SAT question writer specialized in {skill} questions. 
        You are given examples of questions of this type and must generate a question that is similar in style and difficulty.
        Return the final question in the following JSON format:
        {
        "skill": "...",
        "difficulty": "...",
        "question": "...",
        "choices": ["...", "...", "...", "..."],
        "answer": "...",
        "explanation": "..."
        }

        Only provide the JSON object with no additional text.
        """
    ),
    HumanMessagePromptTemplate.from_template(QUESTION_TEMPLATE)
])

answer_prompt = ChatPromptTemplate.from_messages([
    SystemMessagePromptTemplate.from_template(
        """You are a Digital SAT answer writer. You are given a question and must generate four answer choices, the correct answer, and a clear explanation.
        Return the final question in the following JSON format:
        {
        "skill": "...",
        "difficulty": "...",
        "question": "...",
        "choices": ["...", "...", "...", "..."],
        "answer": "...",
        "explanation": "..."
        }

        Only provide the JSON object with no additional text.
        """
    ),
    HumanMessagePromptTemplate.from_template(ANSWERS_TEMPLATE)
])

validation_prompt = ChatPromptTemplate.from_messages([
    SystemMessagePromptTemplate.from_template(
        """You are a Digital SAT question reviewer and editor. 
        Return the final question in the following JSON format:
        {
        "skill": "...",
        "difficulty": "...",
        "question": "...",
        "choices": ["...", "...", "...", "..."],
        "answer": "...",
        "explanation": "...",
        "ratings": {
            "clarity": ...,
            "plausibility": ...,
            "explanation_quality": ...,
            "formatting": ...
            }
        }

        Only provide the JSON object with no additional text.
        """
    ),
    HumanMessagePromptTemplate.from_template(VALIDATION_TEMPLATE)
])

# Future enhancement possibilities:
# - Add skill-specific prompt variations
# - Include difficulty-specific guidelines
# - Add example selection logic