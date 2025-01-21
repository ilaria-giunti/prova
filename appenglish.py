import os
import pandas as pd 
import streamlit as st
from langchain_openai import ChatOpenAI  # Updated import
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

_=load_dotenv()

# Rest of the code remains the same
class FeedAnalyzer:
    def __init__(self, openai_api_key: str):
        openai_api_key=os.environ.get("OPENAI_API_KEY") 
        self.llm = ChatOpenAI(
            temperature=0.2,
            model="gpt-4o"
        )
    @staticmethod
    def load_excel(file):
        try:
            df = pd.read_excel(file)
            if df.empty:
                raise ValueError("The Excel file is empty")
            
            df.columns = df.columns.str.lower().str.strip()
            
            column_mapping = {
                'title': 'title',
                'description': 'description',
                'price': 'price',
                'availability': 'availability',
                'additional_images': 'additional_image_link'
            }
            
            return df.rename(columns=column_mapping)
        except Exception as e:
            raise Exception(f"Error loading Excel file: {e}")

    def load_examples(self):
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
                
                if example_dict:
                    examples.append(example_dict)
            
            return examples
        except Exception as e:
            print(f"Error loading examples: {e}")
            return []

    def check_prices(self, url):
        try:
            response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
            soup = BeautifulSoup(response.text, 'html.parser')
            
            price = soup.find('span', class_='price')
            sale_price = soup.find('span', class_='sale-price')
            
            return {
                'price': price.text.strip() if price else None,
                'sale_price': sale_price.text.strip() if sale_price else None
            }
        except Exception as e:
            print(f"Error scraping prices: {e}")
            return None

    def analyze_feed(self, feed_data, merchant_url):
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

    @staticmethod
    def format_examples(examples):
        examples_text = ""
        for i, example in enumerate(examples, 1):
            examples_text += f"\\nEXAMPLE {i}:\\n"
            examples_text += f"URL: {example.get('url', '')}\\n"
            examples_text += f"TITLE: {example.get('title', '')}\\n"
            examples_text += f"CUSTOM_LABEL_0: {example.get('custom_label_0', '')}\\n"
            examples_text += f"CUSTOM_LABEL_1: {example.get('custom_label_1', '')}\\n"
        return examples_text

    @staticmethod
    def get_analysis_prompt():
        return '''
        You are an expert in Google Merchant Center. Analyze the feed and provide a structured output as follows:

        1. TITLES
        -Evaluate the titles
        If you find issues, such as titles exceeding 150 characters or missing brand name, flag them, otherwise skip.
        -Provide optimized title examples as follows:

        For each title that needs optimization, directly provide the example:
        OPTIMIZED TITLE: [new title]

        2. IMAGES (only if necessary)
        - Flag if additional_image_link is missing, otherwise skip.
        - Flag if there are fewer than 2 images between image_link and additional_image_link

        3. PRICE (only if necessary):
        - Flag if the price doesn't match the website price

        4. DESCRIPTIONS:
        - Evaluate the descriptions and provide optimized examples:
        OPTIMIZED DESCRIPTION: [new description]

        5. CUSTOM LABELS
        If not present, provide custom_label examples that could be useful for each product:
        PRODUCT: [name]
        - Custom Label 0: [specific suggestion for that product]
        - Custom Label 1: [specific suggestion for that product]
        - Custom Label 2: [specific suggestion for that product]

        6. MISSING REQUIRED FIELDS
        If there are missing required fields for any product, indicate:
        Product name: missing attribute
        - id
        - title 
        - description
        - link
        - image_link
        - availability
        - price
        - google_product_category
        - brand
        - condition
        [list only those actually missing]

        Feed to analyze:
        {feed_data}

        URL: {url}

        Reference examples:
        {examples}

        Price analysis:
        {price_analysis}

        IMPORTANT: 
        - For each title to optimize, always show before and after
        - For each product with missing fields, list only the fields that are actually missing
        - Flag ONLY the problems found. If something is correct, don't mention it
        '''

def main():
    st.set_page_config(
        page_title="Feed Analyzer",
        page_icon="📊",
        layout="wide"
    )
    
    openai_api_key=os.environ.get("OPENAI_API_KEY")

    st.title("📈 Feed Audit and Optimization")
    
    try:
        analyzer = FeedAnalyzer(openai_api_key)
        
        feed_file = st.file_uploader(
            "Select Excel feed file",
            type=["xlsx", "xls"]
        )
        
        if feed_file:
            try:
                url_to_analyze = st.text_input(
                    "URL to analyze",
                    placeholder="https://example.com"
                )
                
                if url_to_analyze:
                    if st.button("Start Analysis"):
                        with st.spinner("Analyzing feed..."):
                            feed_data = analyzer.load_excel(feed_file)
                            results = analyzer.analyze_feed(feed_data, url_to_analyze)
                            
                        st.subheader("Analysis Results")
                        st.markdown(results)
                        
            except Exception as e:
                st.error(f"Error processing feed: {str(e)}")
                
    except Exception as e:
        st.error(f"Error initializing application: {str(e)}")

if __name__ == "__main__":
    main()
