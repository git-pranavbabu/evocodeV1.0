# agents/solution_validator.py
import json
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.pydantic_v1 import BaseModel, Field
from . import llm_provider


class ValidationResult(BaseModel):
    """Result of AI solution validation."""
    is_correct: bool = Field(description="Whether the solution correctly solves the problem")
    feedback: str = Field(description="Specific feedback on what's right or wrong")
    missing_requirements: list = Field(description="List of unmet validation criteria")


def get_solution_validation_chain():
    """Initialize the solution validation chain."""
    llm = llm_provider.get_llm(temperature=0.1)  # Low temperature for consistency
    parser = JsonOutputParser(pydantic_object=ValidationResult)
    
    template = """
    You are a coding instructor evaluating a student's solution to a programming problem.

    **Question**: {question}
    **Expected Output**: {expected_output}
    
    **Student's Code**: 
    ```
    {student_code}
    ```
    
    **Actual Output**: {actual_output}

    **Validation Criteria**:
    {validation_criteria}

    **Your Task**:
    1. Does the student's code produce the expected output?
    2. Does the code fulfill all validation criteria?
    3. Is the approach appropriate for the question asked?
    4. Are there any missing requirements?

    Be strict but fair. The code must actually solve the specific problem, not just run without errors.

    {format_instructions}
    """
    
    prompt = PromptTemplate(
        template=template,
        input_variables=["question", "student_code", "expected_output", "actual_output", "validation_criteria"],
        partial_variables={"format_instructions": parser.get_format_instructions()}
    )
    
    return prompt | llm | parser


def validate_coding_solution(question: str, student_code: str, expected_output: str, 
                           actual_output: str, validation_criteria: list) -> tuple[bool, str]:
    """
    Uses AI to validate if student code actually solves the given question.
    
    Returns:
        tuple[bool, str]: (is_correct, feedback_message)
    """
    try:
        validation_chain = get_solution_validation_chain()
        
        criteria_text = "\n".join(f"- {criteria}" for criteria in validation_criteria)
        
        result = validation_chain.invoke({
            "question": question,
            "student_code": student_code,
            "expected_output": expected_output,
            "actual_output": actual_output,
            "validation_criteria": criteria_text
        })
        
        return (result["is_correct"], result["feedback"])
        
    except Exception as e:
        print(f"Error during AI solution validation: {e}")
        # Fallback: if AI validation fails, do basic output comparison
        basic_correct = actual_output.strip() == expected_output.strip()
        return (basic_correct, f"Basic validation: {'Correct output' if basic_correct else 'Output mismatch'}")
