# agents/content_generator.py
import os
from operator import itemgetter
from google.cloud import secretmanager
import google.auth
import re
import json

from langchain_groq import ChatGroq
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser, JsonOutputParser
from langchain.retrievers import EnsembleRetriever
from langchain_core.pydantic_v1 import BaseModel, Field
from . import llm_provider

from models import UserProfile, Lesson, MixedQuiz, MCQQuestion, CodingQuestion


# Load knowledge graph for topic details
with open('KnowledgeGraph.json', 'r') as f:
    knowledge_graph = json.load(f)


class QuizGenerationResult(BaseModel):
    """Structured result for quiz generation."""
    mcq_questions: list = Field(description="List of 3 MCQ questions")
    coding_question: dict = Field(description="Single coding question with all details")


def get_rag_chain(user_profile: UserProfile):
    """
    Initializes a user-specific RAG chain by combining a global and a personal retriever.
    """
    print("Initializing RAG chain...")
    
    # Secret manager and LLM initialization
    try:
        _, project_id = google.auth.default()
        client = secretmanager.SecretManagerServiceClient()
        name = f"projects/{project_id}/secrets/groq-api-key/versions/latest"
        response = client.access_secret_version(name=name)
        key = response.payload.data.decode("UTF-8").strip()
        os.environ["GROQ_API_KEY"] = key
        print("Successfully loaded Groq API key from Secret Manager.")
    except Exception as e:
        print(f"FATAL: Could not load Groq API key from Secret Manager: {e}")
        raise
        
    llm = llm_provider.get_llm(temperature=0.7)
    
    embeddings = HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2",
        model_kwargs={'device': 'cpu'},
        encode_kwargs={'normalize_embeddings': False}
    )
    
    # --- CREATE TWO RETRIEVERS ---
    # 1. The global retriever for W3Schools content
    global_store = Chroma(
        persist_directory="./chroma_db",
        embedding_function=embeddings,
        collection_name="w3schools_python"
    )
    global_retriever = global_store.as_retriever(search_kwargs={"k": 2})

    # 2. The user-specific retriever
    retriever_list = [global_retriever]
    try:
        # Attempt to load the user's personal collection
        user_store = Chroma(
            persist_directory="./chroma_db",
            embedding_function=embeddings,
            collection_name=user_profile.userId
        )
        user_retriever = user_store.as_retriever(search_kwargs={"k": 2})
        retriever_list.append(user_retriever)
        print(f"Loaded personal knowledge base for user {user_profile.userId}.")
    except Exception:
        # This is expected if the user has no documents yet
        print(f"No personal knowledge base found for user {user_profile.userId}. Using global knowledge base only.")

    # --- COMBINE THEM WITH ENSEMBLE RETRIEVER ---
    ensemble_retriever = EnsembleRetriever(
        retrievers=retriever_list, weights=[0.5, 0.5] # Give equal weight to both sources
    )

    template = """
    You are an expert AI programming tutor. You have access to a global knowledge base and the user's personal notes.
    When generating a lesson, prioritize information from the user's personal notes if it is relevant.

    **User's Learning Style:** {learning_style_tags}
    **Topic to Teach:** {topic}
    **Relevant Information (from global knowledge base and user's notes):**
    {context}

    **Your Task:**
    1. Generate a lesson to teach the user the specified topic, tailored to their learning style.
    2. Generate a simple coding challenge as a quiz.
    3. You MUST format your entire response by wrapping the lesson in <lesson> tags and the quiz in <quiz> tags.
    """
    prompt = PromptTemplate.from_template(template)
    
    rag_chain = (
        {
            "context": itemgetter("topic") | ensemble_retriever, # <-- Use the ensemble
            "topic": itemgetter("topic"),
            "learning_style_tags": itemgetter("learning_style_tags"),
        }
        | prompt
        | llm
        | StrOutputParser()
    )
    
    print("RAG chain initialized successfully.")
    return rag_chain


def get_quiz_generation_chain():
    """Initialize chain for generating mixed quizzes (MCQ + coding)."""
    llm = llm_provider.get_llm(temperature=0.8)  # Higher temperature for creative questions
    parser = JsonOutputParser(pydantic_object=QuizGenerationResult)
    
    template = """
    You are an expert programming instructor creating assessment questions.
    
    **Topic:** {topic_title}
    **Quiz Type:** {quiz_type}
    **Context Information:** {context}
    
    Generate exactly 3 MCQ questions and 1 coding question for this topic.
    
    **MCQ Questions Requirements:**
    - Question 1: Test conceptual understanding (definitions, principles)
    - Question 2: Test application knowledge (when/how to use)
    - Question 3: Test code analysis (identify correct/incorrect usage)
    - Each question must have exactly 4 options (A, B, C, D)
    - Only one correct answer per question
    
    **Coding Question Requirements:**
    - Small, focused problem (2-5 lines of code expected)
    - Test core concept application, not complex algorithms
    - Must be auto-gradable with clear expected output
    - Include specific validation criteria
    
    **Important:** Your response must be valid JSON matching this exact structure:
    {{
        "mcq_questions": [
            {{
                "question": "Question text here?",
                "options": ["Option A", "Option B", "Option C", "Option D"],
                "correct_answer": 0
            }},
            {{
                "question": "Question text here?", 
                "options": ["Option A", "Option B", "Option C", "Option D"],
                "correct_answer": 1
            }},
            {{
                "question": "Question text here?",
                "options": ["Option A", "Option B", "Option C", "Option D"], 
                "correct_answer": 2
            }}
        ],
        "coding_question": {{
            "question": "Write Python code to...",
            "expected_output": "Expected program output",
            "validation_criteria": ["Must create variable named 'x'", "Must print result"],
            "sample_solution": "x = 5\\nprint(x)"
        }}
    }}
    
    {format_instructions}
    """
    
    prompt = PromptTemplate(
        template=template,
        input_variables=["topic_title", "quiz_type", "context"],
        partial_variables={"format_instructions": parser.get_format_instructions()}
    )
    
    return prompt | llm | parser


def generate_content(topic: str, user_profile: UserProfile) -> tuple[str, str]:
    """Generates a personalized lesson using the ensemble RAG chain."""
    print(f"Generating content for topic: '{topic}' for user: '{user_profile.userName}'...")
    
    # The chain is now created on-demand for each user
    chain = get_rag_chain(user_profile)
    
    learning_tags = ", ".join(user_profile.learningProfile.tags) if user_profile.learningProfile.tags else "No specific style preference."
    input_data = { "topic": topic, "learning_style_tags": learning_tags }
    
    raw_output = chain.invoke(input_data)
    
    try:
        lesson_match = re.search(r'<lesson>(.*?)</lesson>', raw_output, re.DOTALL)
        quiz_match = re.search(r'<quiz>(.*?)</quiz>', raw_output, re.DOTALL)
        lesson_content = lesson_match.group(1).strip() if lesson_match else raw_output
        quiz_challenge = quiz_match.group(1).strip() if quiz_match else "No quiz could be generated for this topic."
    except Exception:
        lesson_content = raw_output
        quiz_challenge = "Error parsing the generated quiz."
        
    print("Content generation complete.")
    return (lesson_content, quiz_challenge)


def generate_mixed_quiz(topic_title: str, topic_id: str, quiz_type: str, user_profile: UserProfile) -> MixedQuiz:
    """
    Generate a mixed quiz (3 MCQs + 1 coding question) for a specific topic.
    
    Args:
        topic_title: Human readable topic name
        topic_id: Unique topic identifier
        quiz_type: 'onboarding' or 'post_lesson'
        user_profile: User profile for context
    """
    print(f"Generating {quiz_type} quiz for topic: {topic_title}")
    
    try:
        # Get context information using RAG chain
        rag_chain = get_rag_chain(user_profile)
        context_result = rag_chain.invoke({
            "topic": topic_title,
            "learning_style_tags": ""  # Don't need style tags for quiz generation
        })
        
        # Extract just the context part (before lesson/quiz tags)
        context = context_result.split('<lesson>')[0] if '<lesson>' in context_result else context_result[:500]
        
        # Generate quiz using specialized chain
        quiz_chain = get_quiz_generation_chain()
        quiz_result = quiz_chain.invoke({
            "topic_title": topic_title,
            "quiz_type": quiz_type,
            "context": context
        })
        
        # Convert to Pydantic models
        mcq_questions = [
            MCQQuestion(
                question=mcq["question"],
                options=mcq["options"],
                correct_answer=mcq["correct_answer"]
            ) for mcq in quiz_result["mcq_questions"]
        ]
        
        coding_q = quiz_result["coding_question"]
        coding_question = CodingQuestion(
            question=coding_q["question"],
            expected_output=coding_q["expected_output"],
            validation_criteria=coding_q["validation_criteria"],
            sample_solution=coding_q["sample_solution"]
        )
        
        return MixedQuiz(
            topic_id=topic_id,
            topic_title=topic_title,
            mcq_questions=mcq_questions,
            coding_question=coding_question,
            quiz_type=quiz_type
        )
        
    except Exception as e:
        print(f"Error generating mixed quiz: {e}")
        # Return fallback quiz
        return create_fallback_quiz(topic_title, topic_id, quiz_type)


def create_fallback_quiz(topic_title: str, topic_id: str, quiz_type: str) -> MixedQuiz:
    """Create a basic fallback quiz when AI generation fails."""
    fallback_mcqs = [
        MCQQuestion(
            question=f"What is the main concept in {topic_title}?",
            options=["Option A", "Option B", "Option C", "Option D"],
            correct_answer=0
        ),
        MCQQuestion(
            question=f"When would you use {topic_title}?",
            options=["Always", "Never", "Sometimes", "Depends on context"],
            correct_answer=3
        ),
        MCQQuestion(
            question=f"Which statement about {topic_title} is correct?",
            options=["Statement 1", "Statement 2", "Statement 3", "All of the above"],
            correct_answer=2
        )
    ]
    
    fallback_coding = CodingQuestion(
        question=f"Write a simple example demonstrating {topic_title}",
        expected_output="Hello World",
        validation_criteria=["Must contain print statement"],
        sample_solution="print('Hello World')"
    )
    
    return MixedQuiz(
        topic_id=topic_id,
        topic_title=topic_title,
        mcq_questions=fallback_mcqs,
        coding_question=fallback_coding,
        quiz_type=quiz_type
    )
