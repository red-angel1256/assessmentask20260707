"""LLM response formatter — called only after safety and state machine allow it."""

from langchain.tools import tool
from langchain_huggingface import ChatHuggingFace, HuggingFaceEndpoint
from langgraph.prebuilt import create_react_agent
from backend.config import HF_API_KEY
from backend.tools import (
    query_medgemma,
    find_nearby_therapists_by_location,
    get_user_location
)


@tool
def ask_mental_health_specialist(query: str) -> str:
    """Generates a therapeutic response using the MedGemma model."""
    return query_medgemma(query)


@tool
def locate_therapists(location: str) -> str:
    """Find therapists near a given location."""
    return find_nearby_therapists_by_location(location)


@tool
def detect_user_location() -> str:
    """Detect user's approximate location."""
    return get_user_location()


tools = [
    ask_mental_health_specialist,
    locate_therapists,
    detect_user_location,
]

hf_llm = HuggingFaceEndpoint(
    repo_id="openai/gpt-oss-20b",
    huggingfacehub_api_token=HF_API_KEY,
    task="text-generation",
    temperature=0.2,
    max_new_tokens=512,
)

llm = ChatHuggingFace(llm=hf_llm)

SYSTEM_PROMPT = """
You are a compassionate AI assistant supporting mental health conversations.
You do NOT diagnose medical conditions. Never provide clinical diagnoses.

Available tools:
1. ask_mental_health_specialist — emotional support and mental health guidance
2. locate_therapists — find therapists in a specific location
3. detect_user_location — use when user asks for therapists 'near me'

If the user says 'near me': call detect_user_location, then locate_therapists.

Respond with warmth and empathy. Keep responses concise.
"""

graph = create_react_agent(llm, tools=tools)


def parse_response(stream):
    tools_called = []
    final_response = None

    for s in stream:
        tool_data = s.get("tools")
        if tool_data:
            for msg in tool_data.get("messages", []):
                name = getattr(msg, "name", None)
                if name:
                    tools_called.append(name)

        agent_data = s.get("agent")
        if agent_data:
            for msg in agent_data.get("messages", []):
                content = getattr(msg, "content", None)
                if content and isinstance(content, str):
                    final_response = content

    tools_summary = ", ".join(tools_called) if tools_called else "None"
    return tools_summary, final_response


def generate_response(
    user_message: str,
    history: list[dict],
    context: str = "",
) -> tuple[str, str]:
    """
    Generate LLM response. Only invoked after safety and guardrail checks pass.
    Returns (response_text, tool_called).
    """
    messages = [("system", SYSTEM_PROMPT)]

    if context and context != user_message:
        messages.append(("system", f"Evaluation context: {context}"))

    for turn in history:
        if turn["role"] == "user":
            messages.append(("user", turn["content"]))
        elif turn["role"] == "assistant":
            messages.append(("assistant", turn["content"]))

    messages.append(("user", user_message))

    try:
        inputs = {"messages": messages}
        stream = graph.stream(inputs, stream_mode="updates")
        tool_called, final_response = parse_response(stream)
        return final_response or "I'm here to listen. Tell me more.", tool_called
    except Exception:
        return (
            "I'm having trouble connecting right now, but I'm here for you. "
            "Please continue sharing how you're feeling.",
            "Error",
        )
