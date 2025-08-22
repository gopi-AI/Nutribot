import os, json, requests
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

HF_API_URL = os.getenv("HF_API_URL")  # e.g. https://api-inference.huggingface.co/models/mistralai/Mistral-7B-Instruct-v0.3
HF_API_KEY = os.getenv("HF_API_KEY")

# Load small local nutrition set or your USDA subset (keep it small for memory)
DATA_PATH = os.getenv("NUTRITION_JSON_PATH", "nutrition_data.json")
with open(DATA_PATH, "r", encoding="utf-8") as f:
    nutrition = json.load(f)
foods = nutrition["foods"] if isinstance(nutrition, dict) and "foods" in nutrition else nutrition

app = FastAPI(title="Nutrition Chatbot API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ALLOW_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)

class Query(BaseModel):
    query: str

def retrieve_context(q: str, k: int = 8) -> str:
    ql = q.lower()
    # ultra-simple retrieval: substring filter + naive ranking
    hits = []
    for it in foods:
        name = it.get("name") or it.get("description") or ""
        text = f"{name} | kcal:{it.get('calories')} protein_g:{it.get('protein_g')} carbs_g:{it.get('carbs_g')} fat_g:{it.get('fat_g')} fiber_g:{it.get('fiber_g')}"
        score = sum(word in (name.lower()) for word in ql.split())
        hits.append((score, text))
    hits.sort(key=lambda x: x[0], reverse=True)
    return "\n".join(t for _, t in hits[:k])[:6000]  # keep prompt sane

def call_hf(prompt: str) -> str:
    headers = {"Authorization": f"Bearer {HF_API_KEY}"}
    payload = {"inputs": prompt, "parameters": {"max_new_tokens": 400, "temperature": 0.7}}
    r = requests.post(HF_API_URL, headers=headers, json=payload, timeout=120)
    r.raise_for_status()
    out = r.json()
    if isinstance(out, list) and out and "generated_text" in out[0]:
        return out[0]["generated_text"]
    if isinstance(out, dict) and "generated_text" in out:
        return out["generated_text"]
    # Some endpoints return {"choices":[{"text": "..."}]}
    try:
        return out["choices"][0]["text"]
    except Exception:
        return str(out)

@app.get("/health")
def health():
    return {"status": "ok", "foods_loaded": len(foods)}

@app.post("/chat")
def chat(req: Query):
    ctx = retrieve_context(req.query)
    prompt = f"""
You are a cautious nutrition assistant. Use ONLY the context below for nutrition numbers.
If user has BP/diabetes/kidney/heart/liver issues, keep sodium low, adjust protein/carb realistically.

User Query:
{req.query}

Nutrition Context (foods; per-serving approximations):
{ctx}

Return: A one-shot structured diet plan (breakfast/lunch/dinner + snacks) with kcal, protein_g, carbs_g, fat_g per meal, and a plain-English rationale at the end. Avoid medical claims.
"""
    answer = call_hf(prompt)
    return {"answer": answer}

