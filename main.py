# main.py
from fastapi import FastAPI, HTTPException, UploadFile, File
from google.cloud import firestore
from models import UserProfile, Lesson, QuizSubmission, QuizResult
from agents import ai_tutor, grader, student_model, document_processor, error_analyzer
import traceback

app = FastAPI(
    title="Evocode API",
    description="API for the Evocode Intelligent Tutoring System.",
    version="0.1.0"
)

db = firestore.Client()

@app.post("/onboard", response_model=UserProfile, status_code=201)
def onboard_user(profile: UserProfile):
    user_ref = db.collection('users').document(profile.userId)
    if user_ref.get().exists:
        raise HTTPException(status_code=409, detail="User with this ID already exists.")
    user_data = profile.model_dump()
    user_ref.set(user_data)
    print(f"User {profile.userName} onboarded and saved to Firestore.")
    return profile

@app.get("/users/{user_id}", response_model=UserProfile)
def get_user_profile(user_id: str):
    user_ref = db.collection('users').document(user_id)
    doc = user_ref.get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="User not found.")
    return UserProfile(**doc.to_dict())

@app.get("/lesson/{user_id}", response_model=Lesson) # <-- CHANGE RESPONSE MODEL
def get_lesson(user_id: str):
    user_ref = db.collection('users').document(user_id)
    doc = user_ref.get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="User not found.")
    
    user_profile = UserProfile(**doc.to_dict())
    
    try:
        # ai_tutor.run_learning_loop will now return a Lesson object
        lesson_object = ai_tutor.run_learning_loop(user_profile)
        if not lesson_object:
            raise HTTPException(status_code=404, detail="Could not find the next lesson topic.")
        return lesson_object
    except Exception as e:
        print(f"An error occurred during the learning loop. Full traceback:")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail="An internal error occurred while generating the lesson.")

@app.post("/submit_quiz/{user_id}", response_model=QuizResult)
def submit_quiz(user_id: str, submission: QuizSubmission):
    """
    Grades a user's quiz submission, analyzes errors, and updates their progress.
    """
    # 1. Grade the submission
    is_correct, status, error_details = grader.grade_submission(
        source_code=submission.source_code,
        language_id=submission.language_id
    )
    
    struggled_concept = None
    # 2. If incorrect, analyze the error
    if not is_correct and error_details:
        struggled_concept = error_analyzer.analyze_error(
            topic_id=submission.topic_id,
            source_code=submission.source_code,
            error_message=error_details
        )
    
    # 3. Update the user's profile
    student_model.update_knowledge_state(
        user_id=user_id,
        topic_id=submission.topic_id,
        was_correct=is_correct,
        struggled_concept=struggled_concept
    )
    
    # 4. Return the result
    return QuizResult(
        status=status,
        correct=is_correct,
        message="Your submission has been graded."
    )

@app.post("/users/{user_id}/upload")
async def upload_user_document(user_id: str, file: UploadFile = File(...)):
    """Allows a user to upload a document to their personal knowledge base."""
    # Ensure user exists
    user_ref = db.collection('users').document(user_id)
    if not user_ref.get().exists:
        raise HTTPException(status_code=404, detail="User not found.")

    # Update the check to include .pdf
    if not file.filename.endswith(('.txt', '.md', '.pdf')):
        raise HTTPException(status_code=400, detail="Invalid file type. Please upload a .txt, .md, or .pdf file.")

    # Process and store the document using the raw file object
    success = document_processor.process_and_store_document(
        user_id=user_id,
        file_obj=file.file, # Pass the file object
        filename=file.filename # Pass the filename
    )

    if success:
        return {"message": f"File '{file.filename}' uploaded and processed successfully for user {user_id}."}
    else:
        raise HTTPException(status_code=500, detail="Failed to process and store the document.")