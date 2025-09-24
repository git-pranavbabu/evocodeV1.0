# main.py
from fastapi import FastAPI, HTTPException
from google.cloud import firestore
from models import UserProfile, Lesson
from agents import ai_tutor  
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
