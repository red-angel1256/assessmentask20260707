# Step 1: Imports
import requests
from langchain_community.tools import DuckDuckGoSearchRun
from huggingface_hub import InferenceClient
from backend.config import HF_API_KEY

client = InferenceClient(
    model="alibayram/medgemma-4b-it",
    token=HF_API_KEY
)

def query_medgemma(prompt: str) -> str:
    """
    Calls MedGemma model with a therapist personality profile.
    Returns an empathetic mental health response.
    """

    system_prompt = """You are Dr. Emily Hartman, a warm and experienced clinical psychologist.

Respond with:
- empathy
- emotional validation
- gentle guidance
- open-ended reflection questions
"""

    try:
        response = client.chat_completion(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            max_tokens=350,
            temperature=0.7
        )

        return response.choices[0].message.content

    except Exception:
        return "I'm having technical difficulties right now, but I'm here to listen."

# Step 2: DuckDuckGo therapist search
search = DuckDuckGoSearchRun()


def search_therapists(location: str) -> str:
    """
    Search DuckDuckGo for therapists near a given location.
    """

    query = f"licensed therapists or mental health counseling near {location}"

    try:
        results = search.run(query)
        return results

    except Exception:
        return "Unable to retrieve therapist information right now."

#Step 3: Find NearBy Therapists
def find_nearby_therapists_by_location(location: str) -> str:
    """
    Wrapper function used by the agent to fetch therapists.
    """

    therapists = search_therapists(location)

    return f"Here are some therapists and counseling resources near {location}:\n\n{therapists}"


# Step 4: User location detection
def get_user_location() -> str:
    """
    Detect approximate user location using IP geolocation.
    """

    try:
        response = requests.get("http://ip-api.com/json/")
        data = response.json()

        city = data.get("city")
        region = data.get("regionName")
        country = data.get("country")

        return f"{city}, {region}, {country}"

    except Exception:
        return "Unable to determine the user's location right now."