import os
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

api_key = os.getenv("GROQ_API_KEY")
client = Groq(api_key=api_key)

print("📋 Modelos disponibles en tu cuenta de Groq:\n")
models = client.models.list()

for model in models.data:
    print(f"- {model.id}")
    