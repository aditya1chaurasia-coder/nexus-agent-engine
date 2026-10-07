import os
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

class AppSettings(BaseModel):
    provider: str = os.getenv("LLM_PROVIDER", "groq")
    
    # Ollama settings
    ollama_url: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    ollama_model: str = os.getenv("OLLAMA_MODEL", "llama3:latest")
    
    # Cloud API settings
    cloud_key: str = os.getenv("CLOUD_API_KEY", "")
    cloud_url: str = os.getenv("CLOUD_BASE_URL", "https://api.groq.com/openai/v1")
    cloud_model: str = os.getenv("CLOUD_MODEL", "llama-3.3-70b-versatile")

settings = AppSettings()
