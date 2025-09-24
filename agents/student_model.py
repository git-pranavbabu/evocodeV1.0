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
    Determines the next topic for the user to learn.
    Now returns a dictionary with the topic's title and ID.
    """
    mastered_ids = {concept_id for concept_id in user_profile.knowledgeState.mastered_concepts}

    for category in knowledge_graph.values():
        for topic_title, topic_details in category.items():
            topic_id = topic_details["id"]
            
            # Check if user has already mastered this topic
            if topic_id in mastered_ids:
                continue

            # Check if user has mastered all prerequisites
            prerequisites = set(topic_details["prerequisites"])
            if prerequisites.issubset(mastered_ids):
                # Return both title and ID
                return {"title": topic_title, "id": topic_id}

    return None # Indicates the user has completed all topics

def update_knowledge_state(user_id: str, topic_id: str, was_correct: bool, struggled_concept: str | None = None):
    """
    Updates the user's knowledge state in Firestore.
    If the user failed, it can now record the specific struggled concept.
    """
    print(f"Updating knowledge for user '{user_id}' on topic '{topic_id}'. Correct: {was_correct}")
    user_ref = db.collection('users').document(user_id)
    
    try:
        if was_correct:
            user_ref.update({
                'knowledgeState.mastered_concepts': firestore.ArrayUnion([topic_id]),
                'knowledgeState.struggling_with': firestore.ArrayRemove([topic_id])
            })
        else:
            # If we have a specific concept, add it. Otherwise, add the whole topic ID as a fallback.
            item_to_add = struggled_concept if struggled_concept else topic_id
            user_ref.update({
                'knowledgeState.struggling_with': firestore.ArrayUnion([item_to_add])
            })
        print("User knowledge state updated successfully.")
    except Exception as e:
        print(f"Error updating knowledge state for user {user_id}: {e}")
