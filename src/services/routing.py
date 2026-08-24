import random
from typing import List

# Epsilon-Greedy Bandit for A/B Routing
# Let's assume we have two primary routes/models for a given task.
# epsilon: probability of exploring a random model
EPSILON = 0.2

class RouteBandit:
    def __init__(self, routes: List[str]):
        self.routes = routes
        # In a real app, scores would be loaded from Redis or MLflow
        # {route_name: (total_score, count)}
        self.scores = {r: (0.0, 0) for r in routes}

    def select_route(self) -> str:
        """
        Selects a route using epsilon-greedy strategy.
        """
        if random.random() < EPSILON:
            # Explore
            return random.choice(self.routes)
        else:
            # Exploit: pick the highest average score
            best_route = self.routes[0]
            best_avg = -1.0
            for r, (total, count) in self.scores.items():
                avg = total / count if count > 0 else 0
                if avg > best_avg:
                    best_avg = avg
                    best_route = r
            return best_route

    def update_score(self, route: str, score: float):
        if route in self.scores:
            total, count = self.scores[route]
            self.scores[route] = (total + score, count + 1)

# Global router instance for demonstration
# Example variants: "gpt-4o-mini" vs "gemini-1.5-flash"
main_router = RouteBandit(["gpt-4o-mini", "gemini-1.5-flash"])
