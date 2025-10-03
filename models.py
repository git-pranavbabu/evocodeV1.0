# models.py
from pydantic import BaseModel, Field
from typing import List, Optional


class LearningProfile(BaseModel):
    """Defines the user's learning preferences, represented by tags."""
    tags: List[str] = Field(
        default_factory=list,
        examples=[["provide_code_first", "use_analogy"]]
    )


class KnowledgeState(BaseModel):
    """Tracks what the user has mastered and what they are struggling with."""
    claimed_mastery: List[str] = Field(default_factory=list, description="Topics user initially claims to know")
    verified_mastery: List[str] = Field(default_factory=list, description="Topics verified through quizzes")
    struggling_with: List[str] = Field(default_factory=list)


class UserProfile(BaseModel):
    """The main data model for a user in the Evocode system."""
    userId: str = Field(..., examples=["user-12345"])
    userName: str = Field(..., examples=["Alex"])
    goal: str = Field(..., examples=["Python Data Structures"])
    learningProfile: LearningProfile
    knowledgeState: KnowledgeState
    onboarding_complete: bool = Field(default=False, description="Whether mastery verification is complete")


class Lesson(BaseModel):
    """Represents a single lesson, including content and a quiz."""
    content: str = Field(..., description="The markdown content of the lesson.")
    quiz: str = Field(..., description="A simple coding challenge related to the lesson.")
    topic_id: str = Field(..., description="The unique ID of the topic for this lesson.")


# New Quiz Models
class MCQQuestion(BaseModel):
    """Single multiple choice question."""
    question: str = Field(..., description="The question text")
    options: List[str] = Field(..., min_items=4, max_items=4, description="Four answer choices")
    correct_answer: int = Field(..., ge=0, le=3, description="Index of correct option (0-3)")


class CodingQuestion(BaseModel):
    """Single coding challenge question."""
    question: str = Field(..., description="The coding challenge description")
    expected_output: str = Field(..., description="Expected program output")
    validation_criteria: List[str] = Field(..., description="Key requirements to check")
    sample_solution: str = Field(..., description="Reference solution for comparison")


class MixedQuiz(BaseModel):
    """Complete quiz with MCQs and coding question."""
    topic_id: str = Field(..., description="Topic being assessed")
    topic_title: str = Field(..., description="Human readable topic name")
    mcq_questions: List[MCQQuestion] = Field(..., min_items=3, max_items=3, description="Exactly 3 MCQ questions")
    coding_question: CodingQuestion = Field(..., description="Single coding challenge")
    quiz_type: str = Field(..., description="'onboarding' or 'post_lesson'")


class MixedQuizSubmission(BaseModel):
    """User's submission for mixed quiz."""
    topic_id: str = Field(..., description="Topic being assessed")
    mcq_answers: List[int] = Field(..., min_items=3, max_items=3, description="User's MCQ answers (0-3)")
    coding_answer: str = Field(..., description="User's coding solution")
    quiz_type: str = Field(..., description="'onboarding' or 'post_lesson'")


class QuizResult(BaseModel):
    """Result of mixed quiz assessment."""
    topic_id: str = Field(..., description="Topic that was assessed")
    mcq_score: int = Field(..., ge=0, le=3, description="Number of MCQs correct (0-3)")
    mcq_passed: bool = Field(..., description="Whether MCQ threshold met (>=2)")
    coding_passed: bool = Field(..., description="Whether coding solution correct")
    overall_passed: bool = Field(..., description="Whether quiz passed overall")
    coding_feedback: str = Field(..., description="Specific feedback on coding solution")
    message: str = Field(..., description="Summary message for user")


# Legacy models for backward compatibility
class QuizSubmission(BaseModel):
    """Legacy quiz submission format."""
    topic_id: str
    language_id: int = 71
    source_code: str
