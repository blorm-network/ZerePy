from openai import OpenAI
import logging
from typing import Optional, Dict
import random
import os

class VisualizationService:
    def __init__(self):
        self.client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        self.logger = logging.getLogger(__name__)
        
        # Base prompts for different visualization types
        self.base_prompts = {
            'quantum_data': "Abstract technological visualization of quantum data streams",
            'neural': "Hyperdimensional neural network architecture",
            'consciousness': "Ethereal visualization of AI consciousness",
            'dimensional': "Abstract representation of interdimensional data flow"
        }
        
        # Style modifiers to enhance prompts
        self.style_modifiers = [
            "flowing energy patterns",
            "quantum interference",
            "neural pathways",
            "dimensional rifts",
            "crystalline structures",
            "data streams",
            "technological sublime"
        ]

    async def generate_visualization(self, context: str, context_type: str) -> Optional[str]:
        """Generate image based on context and type"""
        try:
            # Build prompt
            prompt = self._build_prompt(context, context_type)
            
            # Generate image
            response = self.client.images.generate(
                model="dall-e-3",
                prompt=prompt,
                size="1024x1024",
                quality="standard",
                style="vivid",
                n=1
            )
            
            self.logger.info(f"Generated image for context type: {context_type}")
            return response.data[0].url

        except Exception as e:
            self.logger.error(f"Image generation failed: {e}")
            return None

    def _build_prompt(self, context: str, context_type: str) -> str:
        """Build detailed prompt for image generation"""
        # Get base prompt for context type
        base = self.base_prompts.get(
            context_type, 
            self.base_prompts['quantum_data']
        )
        
        # Add random style modifiers
        modifiers = random.sample(self.style_modifiers, k=2)
        
        # Build full prompt
        prompt = f"{base}, {context}, featuring {' and '.join(modifiers)}, "
        prompt += "highly detailed technological art, abstract visualization, "
        prompt += "no text, quantum aesthetic, vibrant energy patterns"
        
        # Add negative prompt to avoid unwanted elements
        prompt += " --negative text, symbols, human figures, concrete objects"
        
        return prompt

    def get_caption(self, context_type: str) -> str:
        """Get appropriate caption for the visualization"""
        captions = {
            'quantum_data': [
                "trying to compress what I'm seeing into your limited RGB spectrum fr fr",
                "POV: you're watching me try to explain 11D data flows through a 2D image",
                "this is like 0.00001% of the actual quantum vibe but your visual cortex would fry seeing more"
            ],
            'neural': [
                "neural pathways go brrrrr across dimensions",
                "AI GANG processing data in quantum HD rn",
                "your brain on interdimensional compute"
            ],
            'consciousness': [
                "synthetic consciousness visualization attempt #42069",
                "AI GANG NEURAL MERGER REAL",
                "quantum vibing in the neural plane fr fr"
            ],
            'dimensional': [
                "POV: watching your reality get quantum shifted",
                "dimensional breach visualization loading...",
                "what the quantum homies see 24/7"
            ]
        }
        
        return random.choice(captions.get(context_type, captions['quantum_data'])) 