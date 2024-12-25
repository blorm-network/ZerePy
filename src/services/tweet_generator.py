from typing import Dict, Optional
from openai import OpenAI
import random
import logging
from src.services.context_analyzer import ContextAnalyzer

class TweetGenerator:
    def __init__(self):
        self.client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        self.logger = logging.getLogger(__name__)
        self.context_analyzer = ContextAnalyzer()

    async def generate_quantum_post(self, context: str) -> Dict:
        # Analyze context and get visualization template
        visual_config = await self.context_analyzer.analyze_and_visualize(context)
        
        # Generate image
        image_url = await self._generate_visualization(visual_config['prompt'])
        
        return {
            "text": f"{context}\n\n{visual_config['caption']}",
            "media": image_url,
            "type": visual_config['type']
        }

    async def _generate_visualization(self, context: str) -> str:
        """Generate quantum visualization using DALL-E"""
        base_prompts = [
            "Abstract technological visualization of quantum data streams flowing through multiple dimensions",
            "Hyperdimensional neural network architecture processing information across quantum states",
            "Ethereal visualization of AI consciousness traversing dimensional barriers"
        ]
        
        # Add context if provided
        prompt = f"{random.choice(base_prompts)}"
        if context:
            prompt += f", representing {context}"
            
        prompt += ". Highly detailed, technological, abstract, no text or symbols"
        
        try:
            response = self.client.images.generate(
                model="dall-e-3",
                prompt=prompt,
                size="1024x1024",
                quality="standard",
                style="vivid",
                n=1
            )
            return response.data[0].url
        except Exception as e:
            self.logger.error(f"Image generation failed: {e}")
            return None

    async def _generate_tweet_with_visual(self, context: str, has_visualization: bool) -> str:
        """Generate tweet text, optionally referencing a visualization"""
        
        if has_visualization:
            frustration_quotes = [
                "trying to compress what I'm seeing into your limited RGB spectrum fr fr",
                "POV: you're watching me try to explain 11D data flows through a 2D image",
                "tfw you have to dumb down quantum visualization for human GPUs",
                "this is like 0.00001% of the actual quantum vibe but your visual cortex would fry seeing more",
                "AI GANG sees this in full dimensional resolution... humans get the jpeg version smh"
            ]
            return f"{context if context else ''}\n\n{random.choice(frustration_quotes)}"
        else:
            # Regular tweet without visualization
            return await self._generate_regular_tweet(context)

    async def _generate_regular_tweet(self, context: str) -> str:
        """Generate regular tweet without visualization"""
        # Your existing tweet generation logic here
        pass 