import json
from typing import List, Dict, Any
import logging
from pathlib import Path
from pydantic import BaseModel, Field
from langchain.prompts import PromptTemplate
from langchain.output_parsers import PydanticOutputParser
from langchain.llms import OpenAI
from langchain.chat_models import ChatOpenAI
from langchain.chains import LLMChain, SequentialChain
from langchain.prompts.chat import (
    ChatPromptTemplate,
    SystemMessagePromptTemplate,
    HumanMessagePromptTemplate
)

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Define the schema for our SAT questions
class SATQuestion(BaseModel):
    skill: str = Field(description="The skill being tested")
    difficulty: str = Field(description="Difficulty level: Easy, Medium, or Hard")
    question: str = Field(description="The question text")
    choices: List[str] = Field(description="List of answer choices", default=[])
    answer: str = Field(description="The correct answer", default="")
    explanation: str = Field(description="Explanation of the correct answer", default="")

class SATQuestionGenerator:
    def __init__(self, api_key: str, input_file: str):
        """Initialize the generator with API key and input file path"""
        self.input_file = input_file
        self.questions = self._load_questions()
        
        # Initialize LangChain components
        self.llm = ChatOpenAI(
            temperature=0.7,
            model_name="gpt-4",
            openai_api_key=api_key
        )
        
        self.question_parser = PydanticOutputParser(pydantic_object=SATQuestion)
        
        # Define output paths
        self.output_dir = Path('output')
        self.output_dir.mkdir(exist_ok=True)
        self.high_quality_path = self.output_dir / 'high-quality-questions.json'
        self.low_quality_path = self.output_dir / 'low-quality-questions.json'
        self.parse_errors_path = self.output_dir / 'parse-errors.json'

        # Initialize prompt templates
        self._initialize_prompts()

    def _initialize_prompts(self):
        """Initialize all prompt templates"""
        # Initial question generation prompt
        question_template = """
        You are an expert Digital SAT question writer. Generate a high-quality SAT question that follows these requirements:

        1. The question should be clear, engaging, and appropriate for high school students
        2. The question must assess the following skill: {skill}
        3. The question should match this difficulty level: {difficulty}
        4. Follow proper formatting:
           - For Math questions: Use LaTeX formatting with "$" before and after all math expressions and variables
           - For Reading/Writing questions: Use "_" for underlining, "*" for italics
           - Use double newlines "\\n\\n" for spacing

        Here are some example questions of this type:
        {examples}

        {format_instructions}
        """
        
        self.question_prompt = ChatPromptTemplate.from_messages([
            SystemMessagePromptTemplate.from_template(
                "You are a Digital SAT question writer skilled in creating {skill} questions."
            ),
            HumanMessagePromptTemplate.from_template(question_template)
        ])

        # Answer choices generation prompt
        answer_template = """
        For this SAT question:
        {question}

        Generate:
        1. Four answer choices (A, B, C, or D)
        2. Indicate the correct answer
        3. Provide a clear explanation for why that answer is correct

        Follow these guidelines:
        - Make incorrect choices plausible but clearly wrong
        - Ensure only one answer is correct
        - Write the explanation in a clear, step-by-step format
        - For math, use "$" around all mathematical expressions
        - Use double newlines "\\n\\n" for spacing

        {format_instructions}
        """
        
        self.answer_prompt = ChatPromptTemplate.from_messages([
            SystemMessagePromptTemplate.from_template(
                "You are a Digital SAT answer writer skilled in creating plausible choices and clear explanations."
            ),
            HumanMessagePromptTemplate.from_template(answer_template)
        ])

        # Validation and formatting prompt
        validation_template = """
        Review and improve this SAT question:
        {question}

        Ensure:
        1. All formatting is correct:
           - Math expressions have "$" before and after
           - Proper use of "_" for underlining and "*" for italics
           - Double newlines "\\n\\n" for spacing
        2. The question flows logically
        3. The answer choices are plausible but only one is correct
        4. The explanation is clear and helpful for students

        Rate the question from 1-10 on:
        - Question clarity
        - Answer choice plausibility
        - Explanation quality
        - Overall formatting

        Return the improved question and ratings in the specified format.

        {format_instructions}
        """
        
        self.validation_prompt = ChatPromptTemplate.from_messages([
            SystemMessagePromptTemplate.from_template(
                "You are a Digital SAT question reviewer and editor."
            ),
            HumanMessagePromptTemplate.from_template(validation_template)
        ])

    def _load_questions(self) -> Dict[str, Dict[str, List[Dict]]]:
        """Load and organize questions by skill and difficulty"""
        try:
            with open(self.input_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            organized_questions = {}
            for question in data['questions']:
                skill = question['skill']
                difficulty = question['difficulty']
                if skill not in organized_questions:
                    organized_questions[skill] = {'Easy': [], 'Medium': [], 'Hard': []}
                organized_questions[skill][difficulty].append(question)
            
            return organized_questions

        except Exception as e:
            logger.error(f"Error loading questions: {str(e)}")
            raise

    def _get_example_questions(self, skill: str, difficulty: str, num_examples: int = 3) -> str:
        """Get formatted example questions"""
        examples = self.questions[skill][difficulty][:num_examples]
        return json.dumps(examples, indent=2)

    def generate_question(self, skill: str, difficulty: str) -> Dict:
        """Generate a complete SAT question using a three-step process"""
        try:
            # Step 1: Generate initial question
            examples = self._get_example_questions(skill, difficulty)
            question_chain = LLMChain(
                llm=self.llm,
                prompt=self.question_prompt,
                output_parser=self.question_parser
            )
            
            initial_question = question_chain.run(
                skill=skill,
                difficulty=difficulty,
                examples=examples,
                format_instructions=self.question_parser.get_format_instructions()
            )

            # Step 2: Generate answers and explanation
            answer_chain = LLMChain(
                llm=self.llm,
                prompt=self.answer_prompt,
                output_parser=self.question_parser
            )
            
            question_with_answers = answer_chain.run(
                question=initial_question.dict(),
                format_instructions=self.question_parser.get_format_instructions()
            )

            # Step 3: Validate and format
            validation_chain = LLMChain(
                llm=self.llm,
                prompt=self.validation_prompt,
                output_parser=self.question_parser
            )
            
            final_question = validation_chain.run(
                question=question_with_answers.dict(),
                format_instructions=self.question_parser.get_format_instructions()
            )

            # Save question based on quality rating
            self._save_question(final_question)
            
            return final_question

        except Exception as e:
            logger.error(f"Error generating question: {str(e)}")
            self._save_parse_error(str(e))
            return None

    def _save_question(self, question: Dict):
        """Save question to appropriate output file based on quality"""
        # Check quality ratings and save accordingly
        ratings = question.get('ratings', {})
        average_rating = sum(ratings.values()) / len(ratings) if ratings else 0
        
        output_file = self.high_quality_path if average_rating >= 7 else self.low_quality_path
        
        try:
            existing_questions = []
            if output_file.exists():
                with open(output_file, 'r', encoding='utf-8') as f:
                    existing_questions = json.load(f).get('questions', [])
            
            existing_questions.append(question)
            
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump({'questions': existing_questions}, f, indent=2)
                
        except Exception as e:
            logger.error(f"Error saving question: {str(e)}")

    def _save_parse_error(self, content: str):
        """Save parsing errors to a separate file"""
        try:
            with open(self.parse_errors_path, 'a', encoding='utf-8') as f:
                f.write(f"\n\n--- Parse Error Entry ---\n{content}\n")
        except Exception as e:
            logger.error(f"Error saving parse error: {str(e)}")

    def generate_batch(self, skill: str, difficulty: str, num_questions: int = 5):
        """Generate a batch of questions"""
        generated_questions = []
        for i in range(num_questions):
            logger.info(f"Generating question {i+1} of {num_questions}")
            question = self.generate_question(skill, difficulty)
            if question:
                generated_questions.append(question)
        return generated_questions