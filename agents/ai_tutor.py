# agents/ai_tutor.py
from models import UserProfile, Lesson, MixedQuiz
from . import student_model, content_generator, content_personalizer


def get_onboarding_quiz(user_profile: UserProfile) -> MixedQuiz | None:
    """
    Generate mastery verification quiz for the next claimed topic during onboarding.
    Returns None if no more claimed topics need verification.
    """
    print(f"\n--- Generating onboarding quiz for {user_profile.userName} ---")
    
    # Get next claimed topic that needs verification
    next_claimed_topic = student_model.get_next_claimed_topic(user_profile)
    
    if not next_claimed_topic:
        print("No more claimed topics to verify. Onboarding should be complete.")
        return None
    
    topic_title = next_claimed_topic["title"]
    topic_id = next_claimed_topic["id"]
    print(f"Generating verification quiz for claimed topic: {topic_title} (ID: {topic_id})")
    
    # Generate mixed quiz for verification
    quiz = content_generator.generate_mixed_quiz(
        topic_title=topic_title,
        topic_id=topic_id,
        quiz_type="onboarding",
        user_profile=user_profile
    )

    from . import grader
    grader.store_quiz_for_grading(quiz, user_profile.userId)
    
    
    print(f"Onboarding quiz generated and stored for topic: {topic_title}")
    return quiz    


def get_post_lesson_quiz(user_profile: UserProfile, topic_id: str) -> MixedQuiz:
    """
    Generate post-lesson quiz for a specific topic after lesson delivery.
    """
    print(f"\n--- Generating post-lesson quiz for topic: {topic_id} ---")
    
    # Find topic title from knowledge graph or use topic_id as fallback
    topic_title = topic_id  # This should be enhanced to lookup actual title
    
    # Generate mixed quiz for post-lesson assessment
    quiz = content_generator.generate_mixed_quiz(
        topic_title=topic_title,
        topic_id=topic_id,
        quiz_type="post_lesson",
        user_profile=user_profile
    )
    
    print(f"Post-lesson quiz generated for topic: {topic_title}")
    return quiz


def run_learning_loop(user_profile: UserProfile) -> Lesson | None:
    """
    The main orchestration logic for regular learning (after onboarding).
    This function is only called when onboarding_complete = True.
    """
    print(f"\n--- Starting learning loop for {user_profile.userName} ---")
    
    # Ensure onboarding is complete
    if not user_profile.onboarding_complete:
        print("ERROR: Cannot start learning loop - onboarding not complete!")
        return None
    
    # Get the next topic from verified mastery progression
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
        
        # Generator returns lesson content and simple quiz (legacy format)
        draft_content, draft_quiz = content_generator.generate_content(topic_title, user_profile)
        
        # Validate lesson content for personalization
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
        return Lesson(
            content="I'm sorry, I'm having trouble generating a lesson for you right now. Please try again later.", 
            quiz="", 
            topic_id=topic_id
        )
    
    print("--- Learning loop finished. Returning lesson object. ---")
    print("NOTE: After this lesson, user should take post-lesson quiz via /post_lesson_quiz endpoint")
    
    return Lesson(
        content=final_content, 
        quiz=final_quiz, 
        topic_id=topic_id
    )


def check_onboarding_status(user_profile: UserProfile) -> dict:
    """
    Check the onboarding status and return detailed information.
    """
    claimed_topics = set(user_profile.knowledgeState.claimed_mastery)
    verified_topics = set(user_profile.knowledgeState.verified_mastery)
    struggling_topics = set(user_profile.knowledgeState.struggling_with)
    
    processed_topics = verified_topics | struggling_topics
    remaining_topics = claimed_topics - processed_topics
    
    return {
        "onboarding_complete": user_profile.onboarding_complete,
        "total_claimed": len(claimed_topics),
        "verified_count": len(verified_topics),
        "struggling_count": len(struggling_topics),
        "remaining_count": len(remaining_topics),
        "next_topic_to_verify": list(remaining_topics)[0] if remaining_topics else None,
        "ready_for_learning": user_profile.onboarding_complete
    }
