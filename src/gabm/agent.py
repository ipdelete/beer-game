import os
from typing import Dict
from openai import OpenAI
from ..engine.state import PositionState

# Configuration defaults for Ollama
DEFAULT_ENDPOINT = "http://localhost:11434/v1"
DEFAULT_MODEL = "mistral:latest"

class GABMAgent:
    def __init__(self, role: str):
        self.role = role
        self.endpoint = os.getenv("LLM_ENDPOINT", DEFAULT_ENDPOINT)
        self.model = os.getenv("LLM_MODEL", DEFAULT_MODEL)
        self.client = OpenAI(base_url=self.endpoint, api_key="ollama")
        
        self.system_prompt = self._get_system_prompt()

    def _get_system_prompt(self) -> str:
        prompts = {
            "Retailer": (
                "You are the Retailer in a beer supply chain. Your goal is to minimize costs. "
                "Inventory costs $0.50 per case/week, and backlogs cost $1.00 per case/week. "
                "You cannot communicate with others in the chain. "
                "You must decide how many cases of beer to order from the Wholesaler based on your "
                "current inventory and backlog. Be realistic about your projections."
            ),
            "Wholesaler": (
                "You are the Wholesaler in a beer supply chain. Your goal is to minimize costs. "
                "Inventory costs $0.50 per case/week, and backlogs cost $1.00 per case/week. "
                "You cannot communicate with others in the chain. "
                "You must decide how many cases of beer to order from the Distributor based on your "
                "current inventory and backlog."
            ),
            "Distributor": (
                "You are the Distributor in a beer supply chain. Your goal is to minimize costs. "
                "Inventory costs $0.50 per case/week, and backlogs cost $1.00 per case/week. "
                "You cannot communicate with others in the chain. "
                "You must decide how many cases of beer to order from the Factory based on your "
                "current inventory and backlog."
            ),
            "Factory": (
                "You are the Factory in a beer supply chain. Your goal is to minimize costs. "
                "Inventory costs $0.50 per case/week, and backlogs cost $1.00 per case/week. "
                "You cannot communicate with others in the chain. "
                "You must decide how many cases of beer to produce (order from yourself) based on "
                "your current inventory and backlog."
            ),
        }
        return prompts.get(self.role, "You are a supply chain manager.")

    def decide_order(self, state: PositionState, turn: int, customer_demand: int = 0) -> int:
        # Prepare the prompt with current state
        prompt = (
            f"Turn: {turn}\n"
            f"Role: {self.role}\n"
            f"Current Inventory: {state.inventory}\n"
            f"Current Backlog: {state.backlog}\n"
        )
        if self.role == "Retailer":
            prompt += f"Current Customer Demand: {customer_demand}\n"
        
        prompt += "\nHow many cases should you order? Provide ONLY the number as your response."

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7
            )
            # Extract number from response
            content = response.choices[0].message.content.strip()
            # Attempt to find the first integer in the response
            import re
            match = re.search(r'\d+', content)
            if match:
                return int(match.group())
            return 0
        except Exception as e:
            print(f"Error getting decision for {self.role}: {e}")
            return 0

def gabm_decision(role: str, pos: PositionState, customer_demand: int, turn: int = 0) -> int:
    """
    Wrapper function to make GABM compatible with the simulation engine.
    Note: The current simulation.py doesn't pass 'turn', so we'll need to update it.
    """
    # To avoid creating a new agent every turn, we should cache them.
    if not hasattr(gabm_decision, "_agents"):
        gabm_decision._agents = {role: GABMAgent(role) for role in ['Retailer', 'Wholesaler', 'Distributor', 'Factory']}
    
    # We'll use a default turn for now since the engine doesnt provide it
    return gabm_decision._agents[role].decide_order(pos, turn, customer_demand)
