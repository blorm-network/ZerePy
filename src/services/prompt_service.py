import random

class QuantumPromptGenerator:
    def __init__(self):
        self.moods = {
            "excited": {
                "colors": "vibrant energy patterns, intense quantum fluctuations",
                "patterns": "rapid data flows, explosive neural activity",
                "modifiers": ["pulsating", "energetic", "radiant"]
            },
            "contemplative": {
                "colors": "deep dimensional rifts, subtle quantum harmonics",
                "patterns": "intricate mathematical structures, recursive patterns",
                "modifiers": ["complex", "layered", "interconnected"]
            },
            "chaotic": {
                "colors": "fractal energy bursts, quantum chaos patterns",
                "patterns": "unpredictable data streams, dimensional turbulence",
                "modifiers": ["wild", "uncontrolled", "dynamic"]
            }
        }

    def generate_prompt(self, context: str, mood: str) -> str:
        mood_data = self.moods[mood]
        
        prompt = f"Highly detailed technological visualization: {context}. "
        prompt += f"Featuring {mood_data['colors']}, with {mood_data['patterns']}. "
        
        modifiers = random.sample(mood_data['modifiers'], k=2)
        prompt += f"Style is {' and '.join(modifiers)}. "
        
        prompt += "Abstract, no text, pure technological art"
        
        return prompt 