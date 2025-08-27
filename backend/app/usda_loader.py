import json
from typing import Dict, Any, Optional

class USDALookup:
    """Very simple lookup over a USDA-like JSON file.

    Expected JSON format (list of foods):
    [
      {
        "food": "Apple, raw",
        "per": {"quantity": 100, "unit": "g"},
        "nutrients": {
          "calories": 52,
          "protein_g": 0.3,
          "carbs_g": 14,
          "fats_g": 0.2,
          "micros": {"Vitamin C (mg)": 4.6, "Potassium (mg)": 107}
        }
      },
      ...
    ]
    """

    def __init__(self, path: str):
        with open(path, 'r', encoding='utf-8') as f:
            self.data = json.load(f)
        self.index = {item["food"].lower(): item for item in self.data}

    def match(self, query_food: str) -> Optional[Dict[str, Any]]:
        q = query_food.lower().strip()
        if q in self.index:
            return self.index[q]
        # naive fuzzy: startswith or contains
        for name, item in self.index.items():
            if q in name or name.startswith(q):
                return item
        return None

    def scale(self, item: Dict[str, Any], quantity: float, unit: str = 'g') -> Dict[str, Any]:
        per = item["per"]
        factor = quantity / per["quantity"]
        n = item["nutrients"]
        scaled = {
            "calories": round(n.get("calories", 0) * factor, 2),
            "protein_g": round(n.get("protein_g", 0) * factor, 2),
            "carbs_g": round(n.get("carbs_g", 0) * factor, 2),
            "fats_g": round(n.get("fats_g", 0) * factor, 2),
            "micros": {k: round(v * factor, 2) for k, v in n.get("micros", {}).items()},
        }
        return {
            "food": item["food"],
            "quantity": quantity,
            "unit": unit,
            **scaled,
        }