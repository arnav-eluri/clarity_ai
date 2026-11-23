"""Run: python test_models.py — tests each free model with a real call."""
import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("OPENROUTER_API_KEY") or os.getenv("GEMINI_API_KEY")
client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key)

CANDIDATES = [
    "nvidia/nemotron-3.5-lightning:free",
    "nvidia/nemotron-3-ultra-550b-a55b:free",
    "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
    "google/gemma-4-31b-it:free",
    "google/gemma-4-26b-a4b-it:free",
    "baidu/ernie-5.5-flash-preview:free",
    "inclusionai/ling-3.2-flash:free",
    "particle-ai/particle-1:free",
    "openrouter/free",
]

print("Testing...\n")
for model in CANDIDATES:
    try:
        r = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "Reply with just the word OK"}],
            max_tokens=10,
        )
        print(f"  OK   {model}  -> '{r.choices[0].message.content.strip()}'")
    except Exception as e:
        print(f"  FAIL {model}  — {str(e)[:100]}")
