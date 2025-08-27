from pydantic import BaseModel
from typing import Any, Dict, Optional

class ChatRequest(BaseModel):
    message: str

class NutritionData(BaseModel):
    food: str
    quantity: float
    unit: str | None = None
    calories: float | None = None
    protein_g: float | None = None
    carbs_g: float | None = None
    fats_g: float | None = None
    micros: Dict[str, Any] | None = None

class ChatResponse(BaseModel):
    type: str  # "text" | "nutrition"
    text: str
    data: Optional[NutritionData] = None