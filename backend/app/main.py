import os
import re
import json
from pathlib import Path
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .rag import RAGPipeline  # simple TF-IDF RAG you installed earlier

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
USDA_FILE = DATA_DIR / "usda.json"  # small list of foods like earlier sample

# ---------- Load USDA JSON (small) ----------
def load_usda():
    if not USDA_FILE.exists():
        return []
    with USDA_FILE.open("r", encoding="utf-8") as f:
        return json.load(f)

USDA_DATA = load_usda()


# ---------- Simple USDALookup (name-based) ----------
class USDALookup:
    def __init__(self, data):
        self.data = data or []
        self.index = {item["food"].lower(): item for item in self.data}

    def match(self, query_food: str):
        q = query_food.lower().strip()
        if q in self.index:
            return self.index[q]
        # naive contains/startswith
        for name, item in self.index.items():
            if q in name or name.startswith(q):
                return item
        return None

    def scale(self, item: dict, grams: float = 100.0):
        per = item.get("per", {"quantity": 100})
        factor = grams / float(per.get("quantity", 100))
        n = item.get("nutrients", {})
        scaled = {
            "food": item.get("food"),
            "quantity": grams,
            "unit": "g",
            "calories": round(n.get("calories", 0) * factor, 2),
            "protein_g": round(n.get("protein_g", 0) * factor, 2),
            "carbs_g": round(n.get("carbs_g", 0) * factor, 2),
            "fats_g": round(n.get("fats_g", 0) * factor, 2),
            "micros": {k: round(v * factor, 2) for k, v in n.get("micros", {}).items()},
        }
        return scaled

usda_lookup = USDALookup(USDA_DATA)


# ---------- Request/Response models ----------
class Profile(BaseModel):
    gender: str = Field(..., description="male or female")
    age: int
    height_cm: float
    weight_kg: float
    activity: Optional[str] = Field(None, description="sedentary, light, moderate, active, very_active")
    goal: Optional[str] = Field(None, description="muscle, weight_loss, weight_gain, maintenance")
    conditions: Optional[List[str]] = Field(default_factory=list, description="diabetic, hypertension, kidney, heart, etc.")

class ChatRequest(BaseModel):
    message: Optional[str] = Field(None, description="Free-text query")
    profile: Optional[Profile] = None

class NutritionData(BaseModel):
    food: str
    quantity: float
    unit: str
    calories: Optional[float]
    protein_g: Optional[float]
    carbs_g: Optional[float]
    fats_g: Optional[float]
    micros: Optional[Dict[str, Any]] = None

class ChatResponse(BaseModel):
    type: str  # "text" or "nutrition" or "plan"
    text: str
    data: Optional[Any] = None


# ---------- Utilities: parse quantity/unit (hardcoded servings) ----------
# Hardcoded serving table (extendable)
USDA_SERVINGS = {
    "apple": {"unit": 100, "medium": 182, "small": 149, "large": 223},
    "banana": {"unit": 100, "medium": 118, "small": 101, "large": 136},
    "egg": {"unit": 50, "large": 50},
    "milk": {"cup": 244, "unit": 244},
    "rice": {"cup": 158, "unit": 158},
    "bread": {"slice": 25, "unit": 25},
    "chicken breast": {"unit": 120},
    # add more as needed
}

UNIT_TO_GRAMS = {
    "g": 1,
    "gram": 1,
    "grams": 1,
    "kg": 1000,
    "ml": 1,
    "l": 1000,
    "cup": 150,
    "cups": 150,
    "tbsp": 15,
    "tablespoon": 15,
    "tsp": 5,
    "teaspoon": 5,
    "slice": 25,
    "piece": 100,
}

_qty_re = re.compile(r"(\d+\.?\d*)\s*(\w+)?", flags=re.IGNORECASE)

def parse_quantity_unit(query: str, food: str, default_qty=100.0):
    """
    Attempt to parse a numeric quantity and unit from query.
    Priority:
     1. If food exists in USDA_SERVINGS -> use those sizes
     2. Else try generic unit map
     3. Else default to default_qty grams
    Returns: (grams, unit_str)
    """
    q = (query or "").lower()
    food_key = food.lower()
    # check USDA_SERVINGS
    if food_key in USDA_SERVINGS:
        serving_map = USDA_SERVINGS[food_key]
        # look for size keywords first (e.g., "medium")
        for size_key, grams in serving_map.items():
            if size_key in q:
                # if there's also a number before (e.g., "2 medium apples"), multiply
                m = _qty_re.search(q)
                if m and m.group(2) and not m.group(2).isalpha():  # if unit was numeric only
                    num = float(m.group(1))
                else:
                    # if there's an explicit number
                    num_match = re.search(r"(\d+\.?\d*)", q)
                    num = float(num_match.group(1)) if num_match else 1.0
                return num * float(grams), size_key
        # fallback: if "2 apples" (plural) or no size found
        num_match = re.search(r"(\d+\.?\d*)", q)
        if num_match:
            num = float(num_match.group(1))
            grams = serving_map.get("unit", default_qty)
            return num * float(grams), "unit"
        return float(serving_map.get("unit", default_qty)), "unit"

    # generic parse
    m = _qty_re.search(q)
    if m:
        qty = float(m.group(1))
        unit = (m.group(2) or "g").lower()
        if unit in UNIT_TO_GRAMS:
            grams = qty * UNIT_TO_GRAMS[unit]
            return grams, unit
        # unknown unit: treat number as grams
        return qty, "g"

    return default_qty, "g"


# ---------- Energy & macronutrient calculations ----------
def calc_bmr(gender: str, weight_kg: float, height_cm: float, age: int) -> float:
    """Mifflin-St Jeor equation"""
    gender = gender.lower()
    if gender.startswith("m"):
        bmr = 10 * weight_kg + 6.25 * height_cm - 5 * age + 5
    else:
        bmr = 10 * weight_kg + 6.25 * height_cm - 5 * age - 161
    return float(round(bmr, 2))

ACTIVITY_FACTORS = {
    "sedentary": 1.2,
    "light": 1.375,
    "moderate": 1.55,
    "active": 1.725,
    "very_active": 1.9,
}

def apply_activity(bmr: float, activity: Optional[str]) -> float:
    if not activity:
        return bmr * ACTIVITY_FACTORS["sedentary"]
    key = activity.lower()
    return bmr * ACTIVITY_FACTORS.get(key, ACTIVITY_FACTORS["sedentary"])

def adjust_for_goal(maintenance_cal: float, goal: Optional[str]) -> float:
    if not goal:
        return maintenance_cal
    g = goal.lower()
    if "weight_loss" in g or "loss" in g:
        return maintenance_cal - 500
    if "weight_gain" in g or "gain" in g:
        return maintenance_cal + 500
    if "muscle" in g or "bulking" in g:
        # moderate surplus
        return maintenance_cal + 250
    return maintenance_cal


def calc_macros(total_cal: float, weight_kg: float, goal: Optional[str]) -> Dict[str, float]:
    """
    Return macronutrient targets in grams:
    - protein_g (1.6-2.2 g/kg for muscle; lower for maintenance/loss)
    - fat_g (20-30% kcal)
    - carbs_g remaining kcal
    """
    g = (goal or "").lower()
    # protein per kg
    if "muscle" in g:
        protein_per_kg = 2.0
    elif "weight_loss" in g:
        protein_per_kg = 1.8
    else:
        protein_per_kg = 1.2

    protein_g = round(protein_per_kg * weight_kg, 1)
    protein_cal = protein_g * 4

    # fat percent
    fat_pct = 0.25
    fat_cal = total_cal * fat_pct
    fat_g = round(fat_cal / 9, 1)

    # carbs = remainder
    remaining_cal = max(total_cal - (protein_cal + fat_cal), 0)
    carbs_g = round(remaining_cal / 4, 1)

    return {"protein_g": protein_g, "fat_g": fat_g, "carbs_g": carbs_g}


# ---------- Simple meal template generator ----------
def generate_meal_ideas(goal: str, conditions: List[str]) -> List[str]:
    """Return a short list of meal-suggestion strings tailored to goal + conditions."""
    g = (goal or "").lower()
    conds = [c.lower() for c in (conditions or [])]

    ideas = []

    # protein-focused for muscle
    if "muscle" in g:
        ideas.extend([
            "Grilled chicken breast + quinoa + steamed broccoli (lean protein + carbs + veg).",
            "Greek yogurt bowl with oats, berries and a scoop of whey/plant protein.",
            "Lentil + paneer curry with brown rice (vegetarian high-protein option)."
        ])
    elif "weight_loss" in g:
        ideas.extend([
            "Mixed salad with tuna, lots of leafy greens, cherry tomatoes, olive oil dressing.",
            "Vegetable stir-fry with tofu and a small portion of brown rice.",
            "Oats porridge with berries and a small spoon of nut butter (portion controlled)."
        ])
    elif "weight_gain" in g:
        ideas.extend([
            "Omelette with cheese + whole grain toast + avocado.",
            "Peanut butter banana smoothie with milk and oats.",
            "Salmon with sweet potato and mixed vegetables."
        ])
    else:
        ideas.extend([
            "Balanced plate: lean protein + whole grain carb + 2 servings of vegetables.",
            "Legume-based curry with brown rice and a side salad."
        ])

    # condition-specific adjustments
    if "diabetic" in conds:
        ideas = [i + " (choose low-GI carbs; avoid sugary drinks)." for i in ideas]
    if "hypertension" in conds or "blood pressure" in conds:
        ideas = [i + " (use minimal salt; prefer herbs/spices)." for i in ideas]
    if "kidney" in conds:
        ideas = [i + " (monitor potassium & sodium; consult renal dietitian for protein targets)." for i in ideas]
    if "heart" in conds:
        ideas = [i + " (favor oily fish, nuts; avoid excess saturated fats)." for i in ideas]

    return ideas


# ---------- Init app & RAG ----------
app = FastAPI(title="Nutritional Chatbot API (Profile & RAG)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# init rag pipeline (TF-IDF simple)
try:
    rag = RAGPipeline()
except Exception as e:
    # on startup if RAG fails, print error and set rag to None
    print("RAG init failed:", e)
    rag = None


# ---------- Routes ----------
@app.get("/health")
def health():
    return {"status": "ok", "rag_loaded": rag is not None}

@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    """
    Behavior:
    - If req.profile is provided: produce personalized calorie, macros, meal-ideas, plus RAG explanation.
    - Else if message looks like "X grams of Y" or "apple 150g": try USDA lookup and return nutrition facts + explanation.
    - Else: treat message as general query and pass to RAG for evidence-backed answer.
    """
    # validate input
    if not req.message and not req.profile:
        raise HTTPException(status_code=400, detail="Either 'message' or 'profile' must be provided.")

    # If profile present -> personalized plan
    if req.profile:
        p = req.profile
        # basic validations
        if p.age <= 0 or p.height_cm <= 0 or p.weight_kg <= 0:
            raise HTTPException(status_code=400, detail="Invalid profile numeric values.")

        bmr = calc_bmr(p.gender, p.weight_kg, p.height_cm, p.age)
        maintenance = apply_activity(bmr, p.activity)
        target_cal = adjust_for_goal(maintenance, p.goal)
        macros = calc_macros(target_cal, p.weight_kg, p.goal)
        meal_ideas = generate_meal_ideas(p.goal or "", p.conditions)

        # Compose a human-friendly plan summary
        plan_text = (
            f"Personalized Nutrition Summary:\n"
            f"- BMR: {bmr:.0f} kcal/day\n"
            f"- Estimated maintenance calories (with activity): {maintenance:.0f} kcal/day\n"
            f"- Target calories (goal={p.goal or 'unspecified'}): {target_cal:.0f} kcal/day\n"
            f"- Macronutrients (approx): Protein {macros['protein_g']} g | "
            f"Carbs {macros['carbs_g']} g | Fat {macros['fat_g']} g\n\n"
            "Sample meal ideas:\n" + "\n".join([f"- {m}" for m in meal_ideas[:6]])
        )

        # Ask RAG for condition-aware explanation (if available)
        rag_text = ""
        if rag:
            try:
                # build a short question for RAG so it cites KB about conditions and diet
                conds = ", ".join(p.conditions) if p.conditions else "none"
                rag_query = (
                    f"User profile: gender={p.gender}, age={p.age}, height_cm={p.height_cm}, weight_kg={p.weight_kg}. "
                    f"Goal={p.goal}. Conditions={conds}. Provide evidence-based dietary advice, mention any condition-specific cautions."
                )
                rag_text = rag.answer(rag_query)
            except Exception as e:
                rag_text = f"(RAG explanation unavailable: {e})"

        full_text = plan_text + "\n\n" + "Explanation:\n" + rag_text

        # Return structured plan data + text explanation
        plan_data = {
            "bmr": round(bmr, 2),
            "maintenance_calories": round(maintenance, 2),
            "target_calories": round(target_cal, 2),
            "macros": macros,
            "sample_meals": meal_ideas,
        }

        return ChatResponse(type="plan", text=full_text, data=plan_data)

    # If no profile, handle message-based queries
    message = (req.message or "").strip()

    # 1) Try small USDA lookup: detect food + qty patterns
    # Example pattern: "apple 150g", "150 g apple", "2 apples", "apple nutrition"
    # We'll attempt to find a food name from USDA_DATA
    matched_item = None
    matched_food_name = None
    for item in USDA_DATA:
        fname = item.get("food", "").lower()
        if not fname:
            continue
        if fname in message.lower() or any(tok in message.lower() for tok in fname.split()):
            # naive match - picks first match
            matched_item = item
            matched_food_name = item.get("food")
            break

    if matched_item:
        grams, unit = parse_quantity_unit(message, matched_food_name, default_qty=100.0)
        scaled = usda_lookup.scale(matched_item, grams)
        explanation = ""
        if rag:
            try:
                # ask rag to explain health impressions for eating this food and mention USDA facts
                explanation = rag.answer(f"What are the health implications of consuming {scaled['food']} ({grams} g)?", usda_context=scaled)
            except Exception as e:
                explanation = f"(RAG unavailable: {e})"

        text = f"Nutrition facts for {scaled['food']} ({grams} g):\n" \
               f"- Calories: {scaled.get('calories')} kcal\n" \
               f"- Protein: {scaled.get('protein_g')} g\n" \
               f"- Carbs: {scaled.get('carbs_g')} g\n" \
               f"- Fats: {scaled.get('fats_g')} g\n\n" + explanation

        nutri = NutritionData(
            food=scaled["food"],
            quantity=scaled["quantity"],
            unit=scaled["unit"],
            calories=scaled.get("calories"),
            protein_g=scaled.get("protein_g"),
            carbs_g=scaled.get("carbs_g"),
            fats_g=scaled.get("fats_g"),
            micros=scaled.get("micros"),
        )
        return ChatResponse(type="nutrition", text=text, data=nutri)

    # 2) Fallback: general question -> pass to RAG for evidence-based response
    if rag:
        try:
            answer = rag.answer(message)
            return ChatResponse(type="text", text=answer)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"RAG generation failed: {e}")

    # If RAG not available, return a simple canned response
    return ChatResponse(type="text", text="Sorry — knowledge engine unavailable. Try later.")


# ---------- Local dev run ----------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=int(os.getenv("PORT", 8000)), reload=True)
