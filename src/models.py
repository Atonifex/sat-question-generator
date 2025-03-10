from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict
from enum import Enum

class Difficulty(str, Enum):
    EASY = "Easy"
    MEDIUM = "Medium"
    HARD = "Hard"

class SATQuestion(BaseModel):
    """Pydantic model for SAT question structure"""
    skill: str = Field(description="The skill being tested")
    difficulty: str = Field(description="Difficulty level: Easy, Medium, or Hard")
    question: str = Field(description="The question text")
    choices: List[str] = Field(description="List of answer choices: A, B, C, and D unless it's a free response Math question", default=[])
    answer: str = Field(description="The correct answer: A, B, C, or D unless it's a free response Math question, in which case it's a number or fraction", default="")
    explanation: str = Field(description="Explanation of the correct answer", default="")

    @validator('choices')
    def validate_choices(cls, v):
        if len(v) > 0 and len(v) != 4:
            raise ValueError('Must have exactly 4 choices when provided')
        return v

    @validator('answer')
    def validate_answer(cls, v, values):
        if v and v not in values.get('choices', []):
            raise ValueError('Answer must be one of the choices')
        return v

class QuestionRating(BaseModel):
    """Pydantic model for question quality ratings"""
    clarity: int = Field(ge=1, le=10, description="Rating for question clarity")
    plausibility: int = Field(ge=1, le=10, description="Rating for answer choice plausibility")
    explanation_quality: int = Field(ge=1, le=10, description="Rating for explanation quality")
    formatting: int = Field(ge=1, le=10, description="Rating for overall formatting")
    
    @property
    def average_rating(self) -> float:
        """Calculate the average rating"""
        return sum([self.clarity, self.plausibility, 
                   self.explanation_quality, self.formatting]) / 4

class GeneratedQuestion(SATQuestion):
    """Extended model for generated questions including ratings"""
    ratings: Optional[QuestionRating] = None
    generation_metadata: Optional[Dict] = Field(default_factory=dict)

    def is_high_quality(self) -> bool:
        """Check if question meets high quality threshold"""
        return self.ratings and self.ratings.average_rating >= 7.0