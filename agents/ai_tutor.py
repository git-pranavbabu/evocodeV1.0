# agents/ai_tutor.py
from models import UserProfile
from . import student_model, content_generator, content_personalizer

def run_learning_loop(user_profile: UserProfile) -> str:
    """
    The main orchestration logic for a user's learning session.
    """
    print(f"\n--- Starting learning loop for {user_profile.userName} ---")
    
    # 1. Get the next topic from the Student Model Agent
    next_topic = student_model.get_next_topic(user_profile)
    
    if not next_topic:
        print("User has completed all topics. Congratulations!")
        return "Congratulations! You have completed your learning goal."

    print(f"Next topic identified: {next_topic}")

    # 2. Content Generation & Personalization Loop
    final_content = ""
    max_retries = 2  # Safeguard against infinite loops

    for attempt in range(max_retries):
        print(f"\n--- Attempt {attempt + 1} of {max_retries} ---")
        
        # Call Content Generator
        draft_content = content_generator.generate_content(next_topic, user_profile)
        
        # Call Content Personalizer for validation
        is_approved, feedback = content_personalizer.personalize_and_validate(
            draft_content, user_profile.learningProfile
        )
        
        if is_approved:
            print("Content approved by personalizer.")
            final_content = draft_content
            break  # Exit the loop on success
        else:
            print(f"Content rejected. Feedback: {feedback}")
            # In a more advanced system, this feedback would be passed back
            # to the generator for a targeted revision. For our MVP, we'll just retry.
            final_content = draft_content # Keep the last version in case all attempts fail

    if not final_content:
         return "I'm sorry, I'm having trouble generating a lesson for you right now. Please try again later."
    
    print("\n--- Learning loop finished. Returning final content. ---")
    return final_content