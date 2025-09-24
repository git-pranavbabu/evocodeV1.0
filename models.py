# models.py
from pydantic import BaseModel, Field
from typing import List

class LearningProfile(BaseModel):
    """Defines the user's learning preferences, represented by tags."""
    tags: List[str] = Field(
        default_factory=list,
        examples=[["provide_code_first", "use_analogy"]]
    )

class KnowledgeState(BaseModel):
    """Tracks what the user has mastered and what they are struggling with."""
    mastered_concepts: List[str] = Field(default_factory=list)
    struggling_with: List[str] = Field(default_factory=list)

class UserProfile(BaseModel):
    """The main data model for a user in the Evocode system."""
    userId: str = Field(..., examples=["user-12345"])
    userName: str = Field(..., examples=["Alex"])
    goal: str = Field(..., examples=["Python Data Structures"])
    learningProfile: LearningProfile
    knowledgeState: KnowledgeState

class Lesson(BaseModel):
    """Represents a single lesson, including content and a quiz."""
    content: str = Field(..., description="The markdown content of the lesson.")
    quiz: str = Field(..., description="A simple coding challenge related to the lesson.")
    topic_id: str = Field(..., description="The unique ID of the topic for this lesson.")

class QuizSubmission(BaseModel):
    """Data model for a user's quiz submission."""
    topic_id: str
    language_id: int = 71  # 71 is the Judge0 ID for Python
    source_code: str

class QuizResult(BaseModel):
    """Data model for the result of a quiz submission."""
    status: str
    correct: bool
    message: str