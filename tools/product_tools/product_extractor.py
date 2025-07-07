"""
ProductExtractor - LLM-powered data extraction with validation
Wraps existing llm_invocator with updated OpenAI API and typed Product objects
"""

import json
import logging
import sys
from pathlib import Path
from typing import Dict, Any, Optional, List
from openai import AsyncOpenAI
import asyncio

# Add tools directory to path
sys.path.append(str(Path(__file__).parent.parent.parent / 'tools'))

# Import existing components
from html_processor import ProcessedHTML
from prompt_templator import PromptTemplator

# Import new components
from models.schemas import Product
from config.settings import get_settings

logger = logging.getLogger(__name__)


class ProductExtractor:
    """Extract structured product data using LLM with validation"""
    
    def __init__(self):
        """Initialize product extractor"""
        self.settings = get_settings()
        self.client = AsyncOpenAI(api_key=self.settings.openai_api_key)
        self.prompt_templator = PromptTemplator()
        
        # Extraction parameters
        self.model = self.settings.llm_model
        self.temperature = self.settings.llm_temperature
        self.max_tokens = self.settings.llm_max_tokens
    
    async def extract(self, content: ProcessedHTML, project_id: str = "") -> Product:
        """Extract structured data from processed HTML"""
        try:
            # Generate extraction prompt
            prompt = self._create_extraction_prompt(content)
            
            # Call LLM with updated API
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert at extracting product specifications from web content. Always respond with valid JSON."
                    },
                    {
                        "role": "user", 
                        "content": prompt
                    }
                ],
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                response_format={"type": "json_object"}
            )
            
            # Parse JSON response
            extracted_data = json.loads(response.choices[0].message.content)
            
            # Validate and create Product object
            product = self._create_product_from_extraction(
                extracted_data, 
                content, 
                project_id
            )
            
            # Calculate confidence score
            confidence = self._calculate_confidence(extracted_data, content)
            product.confidence_score = confidence
            
            logger.debug(f"Extracted product data with confidence {confidence:.2f}")
            return product
            
        except Exception as e:
            logger.error(f"Failed to extract product data: {e}")
            # Return basic product with low confidence
            return self._create_fallback_product(content, project_id, str(e))
    
    async def extract_batch(self, content_list: List[ProcessedHTML], project_id: str = "") -> List[Product]:
        """Extract data from multiple HTML contents concurrently"""
        try:
            # Create extraction tasks
            tasks = [
                self.extract(content, project_id)
                for content in content_list
            ]
            
            # Process with concurrency limit
            semaphore = asyncio.Semaphore(3)  # Limit concurrent LLM calls
            
            async def limited_extract(content):
                async with semaphore:
                    return await self.extract(content, project_id)
            
            tasks = [limited_extract(content) for content in content_list]
            products = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Handle exceptions
            result = []
            for i, product in enumerate(products):
                if isinstance(product, Exception):
                    logger.error(f"Exception in batch extraction {i}: {product}")
                    result.append(self._create_fallback_product(
                        content_list[i], project_id, str(product)
                    ))
                else:
                    result.append(product)
            
            return result
            
        except Exception as e:
            logger.error(f"Failed batch extraction: {e}")
            return [
                self._create_fallback_product(content, project_id, str(e))
                for content in content_list
            ]
    
    def validate_extraction(self, product: Product) -> Dict[str, Any]:
        """Validate extracted product data"""
        issues = []
        score = 1.0
        
        # Check required fields
        if not product.description or len(product.description) < 10:
            issues.append("Description too short or missing")
            score -= 0.2
        
        if not product.type or product.type == "Unknown":
            issues.append("Product type not identified")
            score -= 0.1
        
        if not product.image_url:
            issues.append("No product image found")
            score -= 0.1
        
        # Check URL validity
        try:
            if not str(product.url).startswith(('http://', 'https://')):
                issues.append("Invalid product URL")
                score -= 0.1
        except:
            issues.append("Product URL validation failed")
            score -= 0.1
        
        # Check for realistic quantity
        if product.qty <= 0 or product.qty > 1000:
            issues.append("Unrealistic quantity value")
            score -= 0.1
        
        return {
            "is_valid": len(issues) == 0,
            "score": max(0.0, score),
            "issues": issues
        }
    
    def _create_extraction_prompt(self, content: ProcessedHTML) -> str:
        """Create extraction prompt from processed HTML"""
        try:
            # Use existing prompt templator
            prompt = self.prompt_templator.create_product_extraction_prompt(
                content.clean_text,
                content.title,
                content.image_urls
            )
            
            # Enhance with JSON schema requirement
            schema_prompt = """
Extract the following information and return as JSON:
{
    "image_url": "URL of the main product image",
    "type": "Product category (e.g., 'Faucet', 'Cabinet', 'Lighting')",
    "description": "Clear product description with key features",
    "model_no": "Model or part number if available",
    "qty": 1,
    "key": "Unique identifier for Revit (if mentioned)"
}

Ensure all JSON is valid. If information is not available, use null for missing fields.
"""
            
            return prompt + "\n\n" + schema_prompt
            
        except Exception as e:
            logger.error(f"Failed to create extraction prompt: {e}")
            return f"Extract product information from: {content.title}\n{content.clean_text[:1000]}"
    
    def _create_product_from_extraction(self, data: Dict[str, Any], content: ProcessedHTML, project_id: str) -> Product:
        """Create Product object from extracted data"""
        try:
            return Product(
                project_id=project_id,
                url=content.original_url,
                image_url=data.get("image_url") or (content.image_urls[0] if content.image_urls else None),
                type=data.get("type", "Unknown").strip().title(),
                description=data.get("description", content.title or "Product").strip(),
                model_no=data.get("model_no"),
                qty=max(1, int(data.get("qty", 1))),
                key=data.get("key"),
                extraction_metadata={
                    "extraction_method": "llm",
                    "model_used": self.model,
                    "raw_extraction": data,
                    "content_length": len(content.clean_text),
                    "has_images": len(content.image_urls) > 0
                }
            )
            
        except Exception as e:
            logger.error(f"Failed to create product from extraction: {e}")
            return self._create_fallback_product(content, project_id, str(e))
    
    def _create_fallback_product(self, content: ProcessedHTML, project_id: str, error: str) -> Product:
        """Create fallback product when extraction fails"""
        return Product(
            project_id=project_id,
            url=content.original_url,
            image_url=content.image_urls[0] if content.image_urls else None,
            type="Unknown",
            description=content.title or "Product (extraction failed)",
            qty=1,
            confidence_score=0.1,
            extraction_metadata={
                "extraction_method": "fallback",
                "error": error,
                "content_length": len(content.clean_text)
            }
        )
    
    def _calculate_confidence(self, data: Dict[str, Any], content: ProcessedHTML) -> float:
        """Calculate confidence score for extraction"""
        score = 0.5  # Base score
        
        # Add points for extracted fields
        if data.get("description") and len(data["description"]) > 20:
            score += 0.2
        
        if data.get("type") and data["type"] != "Unknown":
            score += 0.1
        
        if data.get("image_url"):
            score += 0.1
        
        if data.get("model_no"):
            score += 0.1
        
        # Check if extraction makes sense
        if content.title and data.get("description"):
            # Simple relevance check
            title_words = set(content.title.lower().split())
            desc_words = set(data["description"].lower().split())
            overlap = len(title_words.intersection(desc_words))
            if overlap > 0:
                score += min(0.1, overlap * 0.02)
        
        return min(1.0, score)