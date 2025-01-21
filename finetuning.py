import pandas as pd
import numpy as np
import json
import os
import random
from langchain_openai import ChatOpenAI
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate

class ConversionTrainer:
    def __init__(self, openai_api_key: str):
        """Initialize the trainer with OpenAI API key."""
        # Rimuovi le virgolette se presenti
        openai_api_key = openai_api_key.strip('"')
        
        if not openai_api_key or openai_api_key == "your-api-key-here":
            raise ValueError("Please provide a valid OpenAI API key")
            
        os.environ["OPENAI_API_KEY"] = openai_api_key
        self.llm = ChatOpenAI(
            temperature=0.7,
            model="gpt-3.5-turbo"
        )
        
        # Sample metrics for training
        self.sample_metrics = [
            {
                "view_item_rate": 45,
                "add_to_cart_rate": 5,
                "checkout_rate": 48,
                "purchase_rate": 8,
                "bottleneck": "view_item"
            },
            {
                "view_item_rate": 55,
                "add_to_cart_rate": 4,
                "checkout_rate": 52,
                "purchase_rate": 12,
                "bottleneck": "add_to_cart"
            },
            {
                "view_item_rate": 52,
                "add_to_cart_rate": 9,
                "checkout_rate": 35,
                "purchase_rate": 11,
                "bottleneck": "checkout"
            }
        ]

    def generate_analysis(self, metrics: dict) -> str:
        """Generate analysis for given metrics."""
        prompt = PromptTemplate(
            template="""
            Given the following e-commerce conversion metrics:

            - View Item Rate: {view_item_rate}% (benchmark: 50%)
            - Add to Cart Rate: {add_to_cart_rate}% (benchmark: 8%)
            - Checkout Rate: {checkout_rate}% (benchmark: 50%)
            - Purchase Rate: {purchase_rate}% (benchmark: 10%)

            Main bottleneck is in the: {bottleneck} phase

            Provide:
            1. A possible cause of the problem
            2. A specific suggestion for improvement
            3. Expected outcome after implementation

            Be concise but specific.
            """,
            input_variables=["view_item_rate", "add_to_cart_rate", "checkout_rate", 
                           "purchase_rate", "bottleneck"]
        )

        chain = LLMChain(llm=self.llm, prompt=prompt)
        return chain.run(metrics)

    def save_feedback(self, metrics: dict, analysis: str, feedback: dict, feedback_file: str = "feedback.jsonl"):
        """Save feedback for an analysis."""
        feedback_entry = {
            "metrics": metrics,
            "analysis": analysis,
            "feedback": feedback
        }
        
        with open(feedback_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(feedback_entry, ensure_ascii=False) + '\n')

    def create_knowledge_base(self, feedback_file: str = "feedback.jsonl", output_dir: str = "knowledge_base"):
        """Create knowledge base files from positive feedback."""
        os.makedirs(output_dir, exist_ok=True)
        
        # Read all feedback
        feedback_entries = []
        try:
            with open(feedback_file, 'r', encoding='utf-8') as f:
                for line in f:
                    feedback_entries.append(json.loads(line))
        except FileNotFoundError:
            print(f"No feedback file found at {feedback_file}")
            return

        # Filter only positive feedback (rating > 3)
        good_feedback = [entry for entry in feedback_entries 
                        if entry['feedback']['rating'] > 3]

        if not good_feedback:
            print("No positive feedback found")
            return

        # Create files for each funnel phase
        phases = {
            'view_item': 'view_item_solutions.txt',
            'add_to_cart': 'add_to_cart_solutions.txt',
            'checkout': 'checkout_solutions.txt',
            'purchase': 'purchase_solutions.txt'
        }

        for phase, filename in phases.items():
            phase_feedback = [entry for entry in good_feedback 
                            if entry['metrics']['bottleneck'] == phase]
            
            if phase_feedback:
                with open(os.path.join(output_dir, filename), 'w', encoding='utf-8') as f:
                    f.write(f"SOLUTIONS FOR {phase.upper()} PHASE\n\n")
                    for entry in phase_feedback:
                        f.write(f"SCENARIO:\n")
                        f.write(f"Metrics: {json.dumps(entry['metrics'], ensure_ascii=False)}\n")
                        f.write(f"ANALYSIS:\n{entry['analysis']}\n")
                        f.write(f"FEEDBACK:\n{entry['feedback']['notes']}\n")
                        f.write("-" * 50 + "\n\n")

def main():
    # Get API key from environment variable or user input
    api_key = os.getenv("OPENAI_API_KEY") or input("Please enter your OpenAI API key: ").strip()
    
    try:
        trainer = ConversionTrainer(api_key)
        
        while True:
            # Choose random metrics
            metrics = random.choice(trainer.sample_metrics)
            
            # Generate analysis
            print("\n" + "="*50)
            print("METRICS:")
            print(f"- View Item Rate: {metrics['view_item_rate']}%")
            print(f"- Add to Cart Rate: {metrics['add_to_cart_rate']}%")
            print(f"- Checkout Rate: {metrics['checkout_rate']}%")
            print(f"- Purchase Rate: {metrics['purchase_rate']}%")
            print(f"\nBottleneck: {metrics['bottleneck']}")
            
            analysis = trainer.generate_analysis(metrics)
            print("\nGENERATED ANALYSIS:")
            print(analysis)
            
            # Collect feedback
            try:
                rating = int(input("\nRate this analysis (1-5): "))
                if 1 <= rating <= 5:
                    notes = input("Additional notes (optional): ")
                    
                    feedback = {
                        "rating": rating,
                        "notes": notes
                    }
                    
                    trainer.save_feedback(metrics, analysis, feedback)
                    
                    if input("\nUpdate knowledge base? (y/n): ").lower() == 'y':
                        trainer.create_knowledge_base()
                else:
                    print("Invalid rating. Please use a number between 1 and 5.")
            except ValueError:
                print("Invalid input. Please enter a number between 1 and 5.")
            
            if input("\nContinue? (y/n): ").lower() != 'y':
                break
                
    except Exception as e:
        print(f"\nError: {str(e)}")

if __name__ == "__main__":
    main()