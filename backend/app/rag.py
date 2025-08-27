import os, json, requests
from pathlib import Path
from typing import List, Dict, Optional
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# ---------- Config ----------
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
KB_DIR = DATA_DIR / "kb"

HF_API_KEY = os.getenv("HF_API_KEY")
HF_GEN_MODEL = os.getenv("HF_GEN_MODEL", "google/flan-t5-large")
HF_API_URL_BASE = "https://api-inference.huggingface.co/models"

SYSTEM_PROMPT = (
    "You are NutriBot, a precise nutrition assistant. Use Evidence + USDA facts to answer. "
    "Be concise, scientific, and cite numbered sources. Always add a disclaimer if medical conditions apply."
)
TOP_K = int(os.getenv("RAG_TOP_K", "3"))

# ---------- Hugging Face helper ----------
def hf_generate(model: str, prompt: str, max_length: int = 400, temperature: float = 0.0) -> str:
    if not HF_API_KEY:
        raise RuntimeError("HF_API_KEY environment variable required.")
    url = f"{HF_API_URL_BASE}/{model}"
    headers = {"Authorization": f"Bearer {HF_API_KEY}"}
    payload = {
        "inputs": prompt,
        "options": {"wait_for_model": True},
        "parameters": {"max_new_tokens": max_length, "temperature": temperature, "return_full_text": False}
    }
    resp = requests.post(url, headers=headers, json=payload, timeout=120)
    resp.raise_for_status()
    res = resp.json()
    if isinstance(res, list) and res and "generated_text" in res[0]:
        return res[0]["generated_text"].strip()
    return str(res)

# ---------- KB loader ----------
class SimpleKB:
    def __init__(self):
        self.docs, self.sources = [], []
        self.vectorizer, self.tfidf_matrix = None, None
        self._load_kb()

    def _load_kb(self):
        if not KB_DIR.exists(): return
        for p in KB_DIR.glob("*.md"):
            raw = p.read_text(encoding="utf-8")
            for i, para in enumerate([x.strip() for x in raw.split("\n\n") if x.strip()]):
                self.docs.append(para)
                self.sources.append(f"{p.name}#para{i}")
        if self.docs:
            self.vectorizer = TfidfVectorizer(max_features=5000, stop_words="english")
            self.tfidf_matrix = self.vectorizer.fit_transform(self.docs)

    def retrieve(self, query: str, top_k: int = TOP_K) -> List[Dict]:
        if not self.docs: return []
        q_vec = self.vectorizer.transform([query])
        sims = cosine_similarity(q_vec, self.tfidf_matrix).flatten()
        ranked = sims.argsort()[::-1][:top_k]
        return [{"text": self.docs[i], "source": self.sources[i], "score": float(sims[i])} for i in ranked]

# ---------- Prompt + Pipeline ----------
def compose_prompt(question: str, retrieved: List[Dict], usda_context: Optional[dict]) -> str:
    parts = [SYSTEM_PROMPT, "\n\nEvidence:\n"]
    if retrieved:
        for i, r in enumerate(retrieved, start=1):
            parts.append(f"[{i}] {r['text']} (Source: {r['source']})\n")
    else:
        parts.append("No evidence found.\n")

    if usda_context:
        parts.append("\nUSDA facts:\n")
        parts.append(json.dumps(usda_context, indent=2))
    parts.append(f"\nQuestion: {question}\nAnswer:\n")
    return "".join(parts)

class RAGPipeline:
    def __init__(self): self.kb = SimpleKB()
    def answer(self, question: str, usda_context: Optional[dict] = None) -> str:
        retrieved = self.kb.retrieve(question)
        prompt = compose_prompt(question, retrieved, usda_context)
        return hf_generate(HF_GEN_MODEL, prompt)

if __name__ == "__main__":
    rag = RAGPipeline()
    print(rag.answer("What foods are good for kidney health?"))
