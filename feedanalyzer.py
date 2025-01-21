import os
import pandas as pd
from typing import List, Dict, Set, Tuple
import docx
import PyPDF2
from langchain.chat_models import ChatOpenAI
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate

class FeedAnalyzer:
    def __init__(self, openai_api_key: str):
        """Initialize the FeedAnalyzer with OpenAI API key."""
        os.environ["OPENAI_API_KEY"] = openai_api_key
        self.llm = ChatOpenAI(
            temperature=0,
            model="gpt-4o"
        )
        self.valid_categories = set()
        self.load_taxonomy()

    def load_taxonomy(self, taxonomy_path: str = "knowledge_base/taxonomy.txt"):
        """Load Google's product taxonomy."""
        try:
            with open(taxonomy_path, 'r', encoding='utf-8') as file:
                # Skip header if present
                for line in file:
                    if not line.startswith('#'):
                        self.valid_categories.add(line.strip())
        except Exception as e:
            print(f"Errore nel caricamento della taxonomy: {e}")
            self.valid_categories = set()

    def suggest_category(self, current_category: str) -> List[str]:
        """Suggest valid categories based on the current invalid one."""
        suggestions = []
        if not current_category:
            return ["Food, Beverages & Tobacco > Food Items > Fresh Food > Fresh Fruits"]
        
        # Convert to lowercase for comparison
        current_lower = current_category.lower()
        
        # Find similar categories
        for valid_cat in self.valid_categories:
            if any(word in valid_cat.lower() for word in current_lower.split()):
                suggestions.append(valid_cat)
                if len(suggestions) >= 3:  # Limit to 3 suggestions
                    break
                    
        return suggestions

    [... previous methods remain the same ...]

    def check_feed_issues(self, df: pd.DataFrame) -> Dict[str, any]:
        """Check for specific issues in the feed."""
        issues = {
            "title_length": [],
            "missing_brand": [],
            "missing_image_column": False,
            "missing_custom_labels": False,
            "invalid_categories": {},
            "missing_category_column": False
        }
        
        # Previous checks remain the same...
        
        # Check for google_product_category column
        if 'google_product_category' not in df.columns:
            issues["missing_category_column"] = True
        else:
            # Check each category
            invalid_cats = {}
            for idx, cat in df['google_product_category'].items():
                if pd.isna(cat) or str(cat).strip() == '':
                    invalid_cats[idx] = {
                        "current": "",
                        "suggestions": ["Food, Beverages & Tobacco > Food Items > Fresh Food > Fresh Fruits"]
                    }
                elif str(cat) not in self.valid_categories:
                    suggestions = self.suggest_category(str(cat))
                    invalid_cats[idx] = {
                        "current": str(cat),
                        "suggestions": suggestions
                    }
            
            if invalid_cats:
                issues["invalid_categories"] = invalid_cats

        return issues

    def analyze_feed(self, excel_path: str, kb_path: str = "knowledge_base"):
        """Analyze the feed data using knowledge base documents."""
        try:
            # Load the feed data
            feed_data = self.load_excel(excel_path)
            
            # Check for specific issues
            issues = self.check_feed_issues(feed_data)
            
            # Load knowledge base content
            knowledge_base = self.read_knowledge_base(kb_path)
            
            fields = [
                'title', 'gtin', 'description', 'availability', 
                'google_product_category', 'custom_label', 
                'additional_image_link', 'price', 'condition'
            ]
            
            available_fields = [f for f in fields if f in feed_data.columns]
            feed_subset = feed_data[available_fields]

            # Prepare issues summary
            issues_summary = ""
            if issues["title_length"]:
                issues_summary += f"\nProdotti con titoli oltre 150 caratteri (righe): {issues['title_length']}"
            if issues["missing_brand"]:
                issues_summary += f"\nProdotti senza brand nel titolo (righe): {issues['missing_brand']}"
            if issues["missing_image_column"]:
                issues_summary += "\nManca la colonna additional_image_link nel feed"
            if issues["missing_custom_labels"]:
                issues_summary += "\nMancano le colonne per le custom label nel feed"
            if issues["missing_category_column"]:
                issues_summary += "\nManca la colonna google_product_category nel feed"
            if issues["invalid_categories"]:
                issues_summary += "\nCategorie non valide trovate nel feed:"
                for idx, data in issues["invalid_categories"].items():
                    current = data["current"] if data["current"] else "VUOTA"
                    issues_summary += f"\nRiga {idx}: Categoria attuale: {current}"
                    if data["suggestions"]:
                        issues_summary += f"\n   Suggerimenti:"
                        for sugg in data["suggestions"]:
                            issues_summary += f"\n   - {sugg}"

            prompt_template = """
            Analizza il seguente feed di prodotti utilizzando come riferimento la knowledge base fornita.
            Concentrati sui problemi rilevati e fornisci suggerimenti specifici per risolverli.

            FEED DATI (prime righe):
            {feed_data}

            PROBLEMI RILEVATI:
            {issues_summary}

            KNOWLEDGE BASE DI RIFERIMENTO:
            {knowledge_base}

            Fornisci un'analisi dettagliata concentrandoti su:

            1. GOOGLE PRODUCT CATEGORY:
            {category_instructions}

            2. STRUTTURA DEL FEED:
            {structural_instructions}

            3. CORREZIONI NECESSARIE PER I TITOLI:
            - Solo se ci sono titoli troppo lunghi, fornisci esempi specifici di come accorciarli
            - Solo per i prodotti senza brand, mostra come aggiungere correttamente "Faan Fruit" all'inizio

            4. CUSTOM LABELS:
            Basandoti sui documenti nella knowledge base, fornisci esempi pratici di custom label per diverse tipologie di prodotto. Per ogni esempio, specifica:
            - Custom Label 0: Categoria principale del prodotto
            - Custom Label 1: Caratteristica distintiva o sottocategoria
            - Custom Label 2: Occasione d'uso o target
            Mostra almeno 3-4 esempi concreti di combinazioni di custom label.

            Fornisci le istruzioni in formato pratico e diretto, concentrandoti solo sui problemi effettivamente presenti nel feed.
            """

            # Prepare category instructions
            category_instructions = ""
            if issues["missing_category_column"]:
                category_instructions += """
                Per aggiungere la colonna google_product_category:
                1. Aggiungi una nuova colonna chiamata "google_product_category"
                2. Usa la categoria corretta dalla taxonomy di Google
                3. Per i prodotti freschi, usa: "Food, Beverages & Tobacco > Food Items > Fresh Food > Fresh Fruits"
                """
            elif issues["invalid_categories"]:
                category_instructions += """
                Correggi le categorie non valide utilizzando i suggerimenti forniti.
                Assicurati di usare ESATTAMENTE le categorie dalla taxonomy di Google, inclusi spazi e simboli '>'
                """

            # Previous instructions preparation remains the same...
            
            prompt = PromptTemplate(
                template=prompt_template,
                input_variables=["feed_data", "issues_summary", "knowledge_base", "structural_instructions", "category_instructions"]
            )

            chain = LLMChain(llm=self.llm, prompt=prompt)
            
            result = chain.run({
                "feed_data": feed_subset.head().to_string(),
                "issues_summary": issues_summary,
                "knowledge_base": knowledge_base,
                "structural_instructions": structural_instructions,
                "category_instructions": category_instructions
            })
            
            return result

        except Exception as e:
            raise Exception(f"Error analyzing feed: {str(e)}")