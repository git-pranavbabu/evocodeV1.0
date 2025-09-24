# agents/student_model.py
import json
from models import UserProfile

# Load the knowledge graph once when the module is imported
with open('KnowledgeGraph.json', 'r') as f:
    knowledge_graph = json.load(f)

def get_next_topic(user_profile: UserProfile) -> str | None:
    """
    Determines the next topic for the user to learn.

    Logic:
    1. Gathers all concepts the user has mastered.
    2. Iterates through all topics in the knowledge graph.
    3. If the user has NOT mastered the current topic's ID,
       and HAS mastered all of its prerequisites, then this is the next topic.
    4. Returns the topic's title (e.g., "Variables and Data Types").
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
                return topic_title # This is the next topic to learn

    return None # Indicates the user has completed all topics