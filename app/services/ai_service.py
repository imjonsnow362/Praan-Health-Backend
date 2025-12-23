import time
import random

class MockAIService:
    """
    Simulates a call to Google Gemini / OpenAI.
    Includes artificial latency to demonstrate 'Async' handling in the API.
    """
    
    @staticmethod
    async def analyze_meal_image(image_path: str):
        # Simulate network latency (1.5 seconds)
        # This justifies why our API endpoint must be `async def`
        time.sleep(1.5) 
        
        # Mock Logic: Randomly determine if it's healthy or not
        # In a real interview, you could mention "Here we would send the image bytes to Vertex AI"
        return {
            "food_items": ["Grilled Chicken", "Brown Rice", "Broccoli"],
            "calories": random.randint(350, 600),
            "macros": {
                "protein_g": random.randint(20, 40),
                "carbs_g": random.randint(30, 60),
                "fats_g": random.randint(5, 15)
            },
            "confidence": 0.94
        }