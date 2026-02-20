from openai import OpenAI
from app.config import BASE_URL
from infra.env import GEMINI_API_KEY


client = OpenAI(
    api_key=GEMINI_API_KEY,
    base_url=BASE_URL,  
    max_retries=0
)