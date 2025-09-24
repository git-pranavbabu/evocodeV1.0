# agents/ai_tutor.py
from models import UserProfile, Lesson # <-- IMPORT Lesson
from . import student_model, content_generator, content_personalizer

def run_learning_loop(user_profile: UserProfile) -> Lesson | None:
    """
    The main orchestration logic. Now returns a Lesson object or None.
    """
    print(f"\n--- Starting learning loop for {user_profile.userName} ---")
    
    # Get the next topic and its ID from the Student Model Agent
    next_topic_info = student_model.get_next_topic(user_profile)
    
    if not next_topic_info:
        print("User has completed all topics. Congratulations!")
        return None

    topic_title = next_topic_info["title"]
    topic_id = next_topic_info["id"]
    print(f"Next topic identified: {topic_title} (ID: {topic_id})")

    # Content Generation & Personalization Loop
    final_content = ""
    final_quiz = ""
    max_retries = 2

    for attempt in range(max_retries):
        print(f"\n--- Attempt {attempt + 1} of {max_retries} ---")
        
        # Generator now returns two items
        draft_content, draft_quiz = content_generator.generate_content(topic_title, user_profile)
        
        # We only need to validate the lesson content for now
        is_approved, feedback = content_personalizer.personalize_and_validate(
            draft_content, user_profile.learningProfile
        )
        
        if is_approved:
            print("Content approved by personalizer.")
            final_content = draft_content
            final_quiz = draft_quiz
            break
        else:
            print(f"Content rejected. Feedback: {feedback}")
            final_content = draft_content # Keep the last version
            final_quiz = draft_quiz

    if not final_content:
        return Lesson(content="I'm sorry, I'm having trouble generating a lesson for you right now. Please try again later.", quiz="", topic_id=topic_id)
    
    print("\n--- Learning loop finished. Returning final lesson object. ---")
    return Lesson(content=final_content, quiz=final_quiz, topic_id=topic_id)