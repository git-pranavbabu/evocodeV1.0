# agents/student_model.py
import json
from models import UserProfile
from google.cloud import firestore


db = firestore.Client()


# Load the knowledge graph once when the module is imported
with open('KnowledgeGraph.json', 'r') as f:
    knowledge_graph = json.load(f)


def get_next_topic(user_profile: UserProfile) -> dict | None:
    """
    Determines the next topic for the user to learn from verified mastery.
    Returns a dictionary with the topic's title and ID.
    """
    # Use verified_mastery instead of mastered_concepts
    verified_ids = set(user_profile.knowledgeState.verified_mastery)

    for category in knowledge_graph.values():
        for topic_title, topic_details in category.items():
            topic_id = topic_details["id"]
            
            # Check if user has already verified this topic
            if topic_id in verified_ids:
                continue

            # Check if user has verified all prerequisites
            prerequisites = set(topic_details["prerequisites"])
            if prerequisites.issubset(verified_ids):
                return {"title": topic_title, "id": topic_id}

    return None  # Indicates the user has completed all topics


def get_next_claimed_topic(user_profile: UserProfile) -> dict | None:
    """
    Gets the next claimed topic that needs verification during onboarding.
    Returns None if all claimed topics have been processed.
    """
    claimed_set = set(user_profile.knowledgeState.claimed_mastery)
    verified_set = set(user_profile.knowledgeState.verified_mastery)
    struggling_set = set(user_profile.knowledgeState.struggling_with)
    
    # Find claimed topics that haven't been verified or marked as struggling
    unprocessed_claimed = claimed_set - verified_set - struggling_set
    
    if not unprocessed_claimed:
        return None
    
    # Get the first unprocessed claimed topic
    next_topic_id = next(iter(unprocessed_claimed))
    
    # Find the topic title from knowledge graph
    for category in knowledge_graph.values():
        for topic_title, topic_details in category.items():
            if topic_details["id"] == next_topic_id:
                return {"title": topic_title, "id": next_topic_id}
    
    return None


def update_mastery_verification(user_id: str, topic_id: str, quiz_passed: bool):
    """
    Updates user's knowledge state after mastery verification quiz.
    """
    print(f"Updating mastery verification for user '{user_id}' on topic '{topic_id}'. Passed: {quiz_passed}")
    user_ref = db.collection('users').document(user_id)
    
    try:
        if quiz_passed:
            # Move from claimed to verified mastery
            user_ref.update({
                'knowledgeState.verified_mastery': firestore.ArrayUnion([topic_id])
            })
            print(f"Topic {topic_id} verified as mastered.")
        else:
            # Move from claimed mastery to struggling with
            user_ref.update({
                'knowledgeState.struggling_with': firestore.ArrayUnion([topic_id])
            })
            print(f"Topic {topic_id} moved to struggling - will need to learn it.")
        
        # Check if onboarding is complete
        doc = user_ref.get()
        if doc.exists:
            user_data = doc.to_dict()
            claimed_count = len(user_data['knowledgeState']['claimed_mastery'])
            verified_count = len(user_data['knowledgeState']['verified_mastery'])
            struggling_count = len(user_data['knowledgeState']['struggling_with'])
            
            if (verified_count + struggling_count) >= claimed_count:
                user_ref.update({'onboarding_complete': True})
                print(f"Onboarding completed for user {user_id}")
                
    except Exception as e:
        print(f"Error updating mastery verification for user {user_id}: {e}")


def update_knowledge_state_mixed(user_id: str, topic_id: str, quiz_passed: bool):
    """
    Updates user's knowledge state after a mixed quiz (post-lesson).
    """
    print(f"Updating knowledge state for user '{user_id}' on topic '{topic_id}'. Passed: {quiz_passed}")
    user_ref = db.collection('users').document(user_id)
    
    try:
        if quiz_passed:
            user_ref.update({
                'knowledgeState.verified_mastery': firestore.ArrayUnion([topic_id]),
                'knowledgeState.struggling_with': firestore.ArrayRemove([topic_id])
            })
            print(f"Topic {topic_id} mastered and verified.")
        else:
            user_ref.update({
                'knowledgeState.struggling_with': firestore.ArrayUnion([topic_id])
            })
            print(f"Topic {topic_id} needs more work - added to struggling list.")
            
    except Exception as e:
        print(f"Error updating knowledge state for user {user_id}: {e}")


# Legacy function for backward compatibility
def update_knowledge_state(user_id: str, topic_id: str, was_correct: bool, struggled_concept: str | None = None):
    """Legacy function for backward compatibility."""
    update_knowledge_state_mixed(user_id, topic_id, was_correct)
