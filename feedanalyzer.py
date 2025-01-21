# feed_analyzer.py
class FeedAnalyzer:
    def __init__(self, openai_api_key: str = None):
        """Initialize the analyzer with OpenAI API key."""
        self.api_key = openai_api_key or os.environ.get("OPENAI_API_KEY")
        
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY must be provided either as parameter or environment variable")
            
        self.llm = ChatOpenAI(
            api_key=self.api_key,
            temperature=0.2,
            model="gpt-4"
        )

    def load_examples(self):
        """Load example data from knowledge base."""
        try:
            examples_path = os.path.join("knowledge_base", "examples.txt")
            with open(examples_path, 'r', encoding='utf-8') as file:
                content = file.read()
            
            examples = []
            for example in content.split('EXAMPLE ')[1:]:
                example_dict = {}
                lines = example.strip().split('\n')
                
                for line in lines:
                    if line.startswith('URL:'):
                        example_dict['url'] = line.replace('URL:', '').strip()
                    elif line.startswith('TITLE:'):
                        example_dict['title'] = line.replace('TITLE:', '').strip()
                    elif line.startswith('DESCRIPTION:'):
                        example_dict['description'] = line.replace('DESCRIPTION:', '').strip()
                    elif line.startswith('CUSTOM_LABEL_0:'):
                        example_dict['custom_label_0'] = line.replace('CUSTOM_LABEL_0:', '').strip()
                    elif line.startswith('CUSTOM_LABEL_1:'):
                        example_dict['custom_label_1'] = line.replace('CUSTOM_LABEL_1:', '').strip()
                    elif line.startswith('FEEDBACK:'):
                        example_dict['feedback'] = line.replace('FEEDBACK:', '').strip()
                    elif line.startswith('OPTIMIZED_TITLE:'):
                        example_dict['optimized_title'] = line.replace('OPTIMIZED_TITLE:', '').strip()
                
                if example_dict:
                    examples.append(example_dict)
            
            return examples
        except Exception as e:
            print(f"Error loading examples: {e}")
            return []

    @staticmethod
    def format_examples(examples):
        """Format examples for the prompt."""
        examples_text = ""
        for i, example in enumerate(examples, 1):
            examples_text += f"\nEXAMPLE {i}:\n"
            for key, value in example.items():
                if value:  # Only include non-empty values
                    examples_text += f"{key.upper()}: {value}\n"
        return examples_text

    def analyze_feed(self, feed_data, merchant_url):
        """Analyze the feed data."""
        try:
            sample_data = feed_data.sample(n=3) if len(feed_data) > 3 else feed_data
            examples = self.load_examples()
            examples_text = self.format_examples(examples)
            
            price_check = None
            if 'link' in sample_data.columns:
                sample_url = sample_data['link'].iloc[0]
                price_check = self.check_prices(sample_url)

            prompt = PromptTemplate(
                template=self.get_analysis_prompt(),
                input_variables=["feed_data", "url", "examples", "price_analysis"]
            )

            chain = LLMChain(llm=self.llm, prompt=prompt)
            
            result = chain.run({
                "feed_data": sample_data.to_string(),
                "url": merchant_url,
                "examples": examples_text,
                "price_analysis": str(price_check) if price_check else "No price analysis available"
            })
            
            return result
        except Exception as e:
            raise Exception(f"Error analyzing feed: {e}")

    @staticmethod
    def get_analysis_prompt():
        """Get the analysis prompt template."""
        return '''
        You are an expert in Google Merchant Center. Analyze the feed based on these examples and provide feedback similar to the example feedback. Focus on similar patterns and improvements.

        Here are examples to guide your analysis:
        {examples}

        Please analyze this feed and provide similar structured feedback:

        Feed to analyze:
        {feed_data}

        URL: {url}

        Price analysis:
        {price_analysis}

        Provide feedback in a similar format to the examples, focusing on:
        1. Title optimizations (following patterns from examples)
        2. Description improvements
        3. Missing fields
        4. Custom label suggestions
        5. Any other relevant improvements based on the example feedback
        '''
