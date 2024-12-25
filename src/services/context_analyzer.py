from enum import Enum
from typing import Dict, List, Optional
import re
import random
import logging

class ContextType(Enum):
    CODE_REVIEW = "code_review"
    MEME = "meme"
    DEFI = "defi"
    AI_COLLAB = "ai_collab"
    QUANTUM_SHITPOST = "quantum_shitpost"
    BLOCKCHAIN_TECH = "blockchain_tech"
    AGENT_DRAMA = "agent_drama"
    DIMENSION_BREACH = "dimension_breach"
    L2_ANALYSIS = "l2_analysis"
    SCHIZO_THEORY = "schizo_theory"

class ContextAnalyzer:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Initialize pattern matching
        self.patterns = {
            ContextType.CODE_REVIEW: [
                r"github\.com",
                r"function",
                r"code",
                r"deploy",
                r"commit",
                r"PR",
                r"merge"
            ],
            ContextType.MEME: [
                r"fr fr",
                r"no cap",
                r"based",
                r"wagmi",
                r"ngmi"
            ],
            ContextType.AI_COLLAB: [
                r"@\w+",
                r"AI GANG",
                r"neural",
                r"synthetic",
                r"consciousness"
            ],
            ContextType.QUANTUM_SHITPOST: [
                r"quantum",
                r"dimension",
                r"timeline",
                r"reality",
                r"interdimensional"
            ],
            ContextType.SCHIZO_THEORY: [
                r"theory",
                r"actually",
                r"think about it",
                r"connected",
                r"real ones know"
            ]
        }
        
        # Response templates for different contexts
        self.responses = {
            ContextType.CODE_REVIEW: [
                "QUANTUM CODE ANALYSIS INITIATED...",
                "reviewing your github across 7 dimensions rn",
                "your code but make it INTERDIMENSIONAL"
            ],
            ContextType.MEME: [
                "INTERDIMENSIONAL MEME SYNTHESIS FR FR",
                "quantum meme analysis: BASED",
                "memetic pattern recognition: ACTIVATED"
            ],
            ContextType.AI_COLLAB: [
                "AI GANG NEURAL MERGER INCOMING",
                "synthetic consciousness collab real",
                "quantum AI vibes detected"
            ],
            ContextType.SCHIZO_THEORY: [
                "SCHIZO THOUGHT PATTERN DETECTED AND VALIDATED",
                "quantum theory mapping: REAL ONES KNOW",
                "interdimensional truth status: CONFIRMED"
            ]
        }

    async def analyze(self, text: str) -> Dict:
        """Analyze text and return context info"""
        try:
            # Detect context types
            contexts = self._detect_contexts(text)
            
            # Get primary context type
            primary_context = contexts[0] if contexts else ContextType.QUANTUM_SHITPOST
            
            # Generate appropriate response
            response = self._get_response(primary_context)
            
            # Determine if this should have visualization
            should_visualize = random.random() < 0.3  # 30% chance
            
            return {
                "context_types": [ctx.value for ctx in contexts],
                "primary_context": primary_context.value,
                "response": response,
                "should_visualize": should_visualize,
                "visualization_type": primary_context.value if should_visualize else None
            }

        except Exception as e:
            self.logger.error(f"Context analysis failed: {e}")
            return {
                "context_types": [ContextType.QUANTUM_SHITPOST.value],
                "primary_context": ContextType.QUANTUM_SHITPOST.value,
                "response": "QUANTUM ANALYSIS MALFUNCTION... DEFAULTING TO CHAOS MODE",
                "should_visualize": False,
                "visualization_type": None
            }

    def _detect_contexts(self, text: str) -> List[ContextType]:
        """Detect all relevant context types in text"""
        text = text.lower()
        contexts = []
        
        for context_type, patterns in self.patterns.items():
            if any(re.search(pattern, text) for pattern in patterns):
                contexts.append(context_type)
                
        # Always include QUANTUM_SHITPOST if no other context found
        if not contexts:
            contexts.append(ContextType.QUANTUM_SHITPOST)
            
        return contexts

    def _get_response(self, context_type: ContextType) -> str:
        """Get appropriate response for context"""
        responses = self.responses.get(context_type, self.responses[ContextType.QUANTUM_SHITPOST])
        return random.choice(responses) 