import json
import re

text = """To effectively target customers in Mumbai, we should consider their current engagement level with our brand. What type of customers in Mumbai would you like to focus on - for instance, those who are active, new, or perhaps lapsed customers who we want to win back? { "response": "To effectively target customers in Mumbai, we should consider their current engagement level with our brand. What type of customers in Mumbai would you like to focus on - for instance, those who are active, new, or perhaps lapsed customers who we want to win back?", "suggestions": [ {"label": "Active customers", "value": "active", "category": "audience"}, {"label": "New customers", "value": "new", "category": "audience"}, {"label": "Lapsed customers", "value": "lapsed", "category": "audience"} ], "brief_updates": {"audience": "customers in Mumbai"}, "ready_to_plan": false }"""

def parse_json_response(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Fallback to regex extraction
        match = re.search(r'(\{.*\})', text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass
        return {}

parsed = parse_json_response(text)
print("Parsed response keys:", list(parsed.keys()))
print("Parsed response text:", parsed.get("response"))
print("Parsed brief_updates:", parsed.get("brief_updates"))
