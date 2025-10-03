# agents/grader.py
import os
import requests
import time
from google.cloud import secretmanager
import google.auth
from models import MixedQuizSubmission, QuizResult, MCQQuestion, CodingQuestion, MixedQuiz
from . import solution_validator
from . import content_generator
import json


judge0_key = None
# In-memory storage for active quizzes (in production, use Redis or database)
active_quizzes = {}
# At the top of grader.py, ensure this exists:
active_quizzes = {}

def store_quiz_for_grading(quiz: MixedQuiz, user_id: str):
    """Store quiz in memory for grading."""
    key = f"{user_id}:{quiz.topic_id}:{quiz.quiz_type}"
    active_quizzes[key] = quiz
    print(f"✅ Stored quiz for grading with key: {key}")


def get_judge0_key():
    """Retrieves the Judge0 API key from Secret Manager."""
    global judge0_key
    if judge0_key is not None:
        return judge0_key

    try:
        _, project_id = google.auth.default()
        client = secretmanager.SecretManagerServiceClient()
        name = f"projects/{project_id}/secrets/judge0-api-key/versions/latest"
        response = client.access_secret_version(name=name)
        judge0_key = response.payload.data.decode("UTF-8").strip()
        print("Successfully loaded Judge0 API key.")
        return judge0_key
    except Exception as e:
        print(f"FATAL: Could not load Judge0 API key: {e}")
        raise


def store_quiz_for_grading(quiz: MixedQuiz, user_id: str):
    """
    Store quiz in memory for grading. In production, use proper storage.
    Key format: f"{user_id}:{topic_id}:{quiz_type}"
    """
    key = f"{user_id}:{quiz.topic_id}:{quiz.quiz_type}"
    active_quizzes[key] = quiz
    print(f"Stored quiz for grading with key: {key}")


def get_stored_quiz(user_id: str, topic_id: str, quiz_type: str) -> MixedQuiz | None:
    """Retrieve stored quiz for grading."""
    key = f"{user_id}:{topic_id}:{quiz_type}"
    return active_quizzes.get(key)


def execute_code_and_get_output(source_code: str, language_id: int = 71) -> tuple[bool, str, str]:
    """
    Enhanced function: Executes code and returns execution success, status, and actual output.
    Returns tuple of (execution_success, status_description, actual_output).
    """
    api_key = get_judge0_key()
    payload = {
        "source_code": source_code,
        "language_id": language_id,
    }

    headers = {
        "content-type": "application/json",
        "X-RapidAPI-Key": api_key,
        "X-RapidAPI-Host": "judge0-ce.p.rapidapi.com"
    }

    # Submit the code
    try:
        response = requests.post("https://judge0-ce.p.rapidapi.com/submissions?base64_encoded=false&wait=false", json=payload, headers=headers)
        response.raise_for_status()
        submission_token = response.json().get('token')
        if not submission_token:
            return (False, "Failed to get submission token.", "")
    except requests.exceptions.RequestException as e:
        return (False, f"API request failed: {e}", "")

    # Poll for the result
    for _ in range(10):
        try:
            response = requests.get(f"https://judge0-ce.p.rapidapi.com/submissions/{submission_token}?base64_encoded=false", headers=headers)
            response.raise_for_status()
            result = response.json()
            status = result.get('status', {})
            status_description = status.get('description', 'Unknown')
            
            if status.get('id', 0) > 2:  # Statuses > 2 indicate completion
                execution_success = (status.get('id') == 3)  # ID 3 is "Accepted" 
                actual_output = result.get('stdout', '').strip()
                
                if not execution_success:
                    # If execution failed, get error message as output
                    error_output = result.get('stderr') or result.get('compile_output') or 'Execution failed'
                    actual_output = error_output
                
                return (execution_success, status_description, actual_output)
                
        except requests.exceptions.RequestException as e:
            return (False, f"API polling failed: {e}", "")
        time.sleep(1)
        
    return (False, "Execution timed out.", "")


def grade_mcq_questions(user_answers: list[int], mcq_questions: list[MCQQuestion]) -> tuple[int, list[bool]]:
    """
    Grade MCQ questions and return score and individual results.
    Returns tuple of (total_correct, individual_results).
    """
    if len(user_answers) != len(mcq_questions):
        print(f"ERROR: Answer count mismatch. Expected {len(mcq_questions)}, got {len(user_answers)}")
        return (0, [False] * len(mcq_questions))
    
    individual_results = []
    total_correct = 0
    
    for i, (user_answer, question) in enumerate(zip(user_answers, mcq_questions)):
        is_correct = user_answer == question.correct_answer
        individual_results.append(is_correct)
        if is_correct:
            total_correct += 1
        
        print(f"MCQ {i+1}: User answered {user_answer}, correct answer is {question.correct_answer} - {'✅' if is_correct else '❌'}")
    
    return (total_correct, individual_results)


def grade_coding_question(student_code: str, coding_question: CodingQuestion) -> tuple[bool, str]:
    """
    Grade a coding question using two-layer validation:
    1. Judge0 execution check
    2. AI solution validation
    
    Returns tuple of (is_correct, feedback_message).
    """
    print(f"Grading coding question with two-layer validation...")
    
    # Layer 1: Execute code and get output
    execution_success, status, actual_output = execute_code_and_get_output(student_code)
    
    if not execution_success:
        return (False, f"Code execution failed: {status}. Error: {actual_output}")
    
    # Layer 2: AI validation of solution correctness
    is_correct_solution, ai_feedback = solution_validator.validate_coding_solution(
        question=coding_question.question,
        student_code=student_code,
        expected_output=coding_question.expected_output,
        actual_output=actual_output,
        validation_criteria=coding_question.validation_criteria
    )
    
    if is_correct_solution:
        feedback = f"✅ Correct! {ai_feedback}"
    else:
        feedback = f"❌ Incorrect. {ai_feedback}"
    
    print(f"Coding question result: {'PASS' if is_correct_solution else 'FAIL'}")
    return (is_correct_solution, feedback)


def grade_mixed_quiz(submission: MixedQuizSubmission) -> QuizResult:
    """
    Grade a complete mixed quiz (3 MCQs + 1 coding question).
    Retrieves the original quiz from storage to grade against.
    """
    print(f"Grading mixed quiz for topic: {submission.topic_id}, type: {submission.quiz_type}")
    
    # Try to retrieve the stored quiz - this is a simplified approach
    # In production, you'd want a more robust storage mechanism
    stored_quiz = None
    for key, quiz in active_quizzes.items():
        if quiz.topic_id == submission.topic_id and quiz.quiz_type == submission.quiz_type:
            stored_quiz = quiz
            break
    
    if not stored_quiz:
        print(f"ERROR: Could not find stored quiz for topic {submission.topic_id}, type {submission.quiz_type}")
        return QuizResult(
            topic_id=submission.topic_id,
            mcq_score=0,
            mcq_passed=False,
            coding_passed=False,
            overall_passed=False,
            coding_feedback="Error: Quiz not found for grading",
            message="Grading failed - quiz not found"
        )
    
    # Grade MCQ questions
    mcq_score, mcq_results = grade_mcq_questions(submission.mcq_answers, stored_quiz.mcq_questions)
    mcq_passed = mcq_score >= 2  # Need at least 2 out of 3 correct
    
    # Grade coding question
    coding_passed, coding_feedback = grade_coding_question(
        submission.coding_answer, 
        stored_quiz.coding_question
    )
    
    # Overall result - both MCQ and coding must pass
    overall_passed = mcq_passed and coding_passed
    
    # Create detailed message
    mcq_emoji = "✅" if mcq_passed else "❌"
    coding_emoji = "✅" if coding_passed else "❌"
    message = f"MCQ: {mcq_score}/3 {mcq_emoji}, Coding: {coding_emoji}"
    
    result = QuizResult(
        topic_id=submission.topic_id,
        mcq_score=mcq_score,
        mcq_passed=mcq_passed,
        coding_passed=coding_passed,
        overall_passed=overall_passed,
        coding_feedback=coding_feedback,
        message=message
    )
    
    print(f"Quiz grading complete. Overall result: {'PASS' if overall_passed else 'FAIL'}")
    return result


# Legacy function for backward compatibility
def grade_submission(source_code: str, language_id: int) -> tuple[bool, str, str | None]:
    """
    Legacy function: Submits code to Judge0 and returns correctness and any error messages.
    Returns a tuple of (is_correct, status_description, error_details).
    """
    execution_success, status, actual_output = execute_code_and_get_output(source_code, language_id)
    
    if execution_success:
        return (True, status, None)
    else:
        return (False, status, actual_output)
