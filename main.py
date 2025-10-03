# main.py
from fastapi import FastAPI, HTTPException, UploadFile, File
from google.cloud import firestore
from models import UserProfile, Lesson, MixedQuiz, MixedQuizSubmission, QuizResult, QuizSubmission
from agents import ai_tutor, grader, student_model, document_processor, error_analyzer
import traceback


app = FastAPI(
    title="Evocode API",
    description="API for the Evocode Intelligent Tutoring System with Enhanced Quiz System.",
    version="1.1.0"
)


db = firestore.Client()


@app.post("/onboard", response_model=UserProfile, status_code=201)
def onboard_user(profile: UserProfile):
    """Enhanced onboarding with claimed mastery tracking."""
    user_ref = db.collection('users').document(profile.userId)
    if user_ref.get().exists:
        raise HTTPException(status_code=409, detail="User with this ID already exists.")
    
    # Ensure onboarding_complete is False for new users
    profile.onboarding_complete = False
    
    user_data = profile.model_dump()
    user_ref.set(user_data)
    print(f"User {profile.userName} onboarded. Claimed mastery: {profile.knowledgeState.claimed_mastery}")
    return profile


@app.get("/users/{user_id}", response_model=UserProfile)
def get_user_profile(user_id: str):
    user_ref = db.collection('users').document(user_id)
    doc = user_ref.get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="User not found.")
    return UserProfile(**doc.to_dict())


@app.get("/verify_mastery/{user_id}", response_model=MixedQuiz)
def get_mastery_verification_quiz(user_id: str):
    """Generate quiz for next claimed mastery topic during onboarding."""
    user_ref = db.collection('users').document(user_id)
    doc = user_ref.get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="User not found.")
    
    user_profile = UserProfile(**doc.to_dict())
    
    if user_profile.onboarding_complete:
        raise HTTPException(status_code=400, detail="User has already completed onboarding.")
    
    try:
        quiz = ai_tutor.get_onboarding_quiz(user_profile)
        if not quiz:
            raise HTTPException(status_code=404, detail="No more claimed topics to verify.")
        return quiz
    except Exception as e:
        print(f"Error generating mastery verification quiz: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate verification quiz.")


@app.post("/submit_mastery_quiz/{user_id}", response_model=QuizResult)
def submit_mastery_verification_quiz(user_id: str, submission: MixedQuizSubmission):
    """Handle mastery verification quiz submission during onboarding."""
    user_ref = db.collection('users').document(user_id)
    doc = user_ref.get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="User not found.")
    
    try:
        result = grader.grade_mixed_quiz(submission)
        student_model.update_mastery_verification(user_id, submission.topic_id, result.overall_passed)
        return result
    except Exception as e:
        print(f"Error processing mastery quiz: {e}")
        raise HTTPException(status_code=500, detail="Failed to process mastery verification.")


@app.get("/lesson/{user_id}", response_model=Lesson)
def get_lesson(user_id: str):
    """Get next lesson (only after onboarding is complete)."""
    user_ref = db.collection('users').document(user_id)
    doc = user_ref.get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="User not found.")
    
    user_profile = UserProfile(**doc.to_dict())
    
    if not user_profile.onboarding_complete:
        raise HTTPException(status_code=400, detail="Please complete onboarding mastery verification first.")
    
    try:
        lesson_object = ai_tutor.run_learning_loop(user_profile)
        if not lesson_object:
            raise HTTPException(status_code=404, detail="Could not find the next lesson topic.")
        return lesson_object
    except Exception as e:
        print(f"An error occurred during the learning loop. Full traceback:")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail="An internal error occurred while generating the lesson.")


@app.get("/post_lesson_quiz/{user_id}", response_model=MixedQuiz)
def get_post_lesson_quiz(user_id: str, topic_id: str):
    """Generate post-lesson quiz for a specific topic."""
    user_ref = db.collection('users').document(user_id)
    doc = user_ref.get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="User not found.")
    
    user_profile = UserProfile(**doc.to_dict())
    
    try:
        quiz = ai_tutor.get_post_lesson_quiz(user_profile, topic_id)
        return quiz
    except Exception as e:
        print(f"Error generating post-lesson quiz: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate post-lesson quiz.")


@app.post("/submit_quiz/{user_id}", response_model=QuizResult)
def submit_quiz(user_id: str, submission: MixedQuizSubmission):
    """Submit mixed quiz (MCQ + coding) for grading."""
    try:
        result = grader.grade_mixed_quiz(submission)
        student_model.update_knowledge_state_mixed(user_id, submission.topic_id, result.overall_passed)
        return result
    except Exception as e:
        print(f"Error processing quiz submission: {e}")
        raise HTTPException(status_code=500, detail="Failed to process quiz submission.")


# Legacy endpoint for backward compatibility
@app.post("/submit_quiz_legacy/{user_id}", response_model=dict)
def submit_quiz_legacy(user_id: str, submission: QuizSubmission):
    """Legacy quiz submission endpoint."""
    is_correct, status, error_details = grader.grade_submission(
        source_code=submission.source_code,
        language_id=submission.language_id
    )
    
    struggled_concept = None
    if not is_correct and error_details:
        struggled_concept = error_analyzer.analyze_error(
            topic_id=submission.topic_id,
            source_code=submission.source_code,
            error_message=error_details
        )
    
    student_model.update_knowledge_state(
        user_id=user_id,
        topic_id=submission.topic_id,
        was_correct=is_correct,
        struggled_concept=struggled_concept
    )
    
    return {
        "status": status,
        "correct": is_correct,
        "message": "Your submission has been graded."
    }


@app.post("/users/{user_id}/upload")
async def upload_user_document(user_id: str, file: UploadFile = File(...)):
    """Allows a user to upload a document to their personal knowledge base."""
    user_ref = db.collection('users').document(user_id)
    if not user_ref.get().exists:
        raise HTTPException(status_code=404, detail="User not found.")

    if not file.filename.endswith(('.txt', '.md', '.pdf')):
        raise HTTPException(status_code=400, detail="Invalid file type. Please upload a .txt, .md, or .pdf file.")

    success = document_processor.process_and_store_document(
        user_id=user_id,
        file_obj=file.file,
        filename=file.filename
    )

    if success:
        return {"message": f"File '{file.filename}' uploaded and processed successfully for user {user_id}."}
    else:
        raise HTTPException(status_code=500, detail="Failed to process and store the document.")


@app.get("/onboarding_status/{user_id}")
def get_onboarding_status(user_id: str):
    """Check if user has completed onboarding."""
    user_ref = db.collection('users').document(user_id)
    doc = user_ref.get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="User not found.")
    
    user_profile = UserProfile(**doc.to_dict())
    
    return {
        "onboarding_complete": user_profile.onboarding_complete,
        "claimed_topics": user_profile.knowledgeState.claimed_mastery,
        "verified_topics": user_profile.knowledgeState.verified_mastery,
        "remaining_verifications": len(user_profile.knowledgeState.claimed_mastery) - len(user_profile.knowledgeState.verified_mastery)
    }
