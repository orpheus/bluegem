"""
RevitConnector - Revit integration and field mapping
Ensures compatibility with Revit schedules and family parameters
"""

import logging
import re
from typing import List, Dict, Any, Optional, Tuple
from models.schemas import Product
from config.settings import get_settings

logger = logging.getLogger(__name__)


class RevitConnector:
    """Handle Revit-specific field mapping and validation"""
    
    def __init__(self):
        """Initialize Revit connector"""
        self.settings = get_settings()
        
        # Revit parameter mappings
        self.revit_parameters = {
            # Built-in Revit parameters
            "Type Name": "type",
            "Type Comments": "description", 
            "Model": "model_no",
            "Manufacturer": "manufacturer",
            "Type Image": "image_url",
            "URL": "url",
            "Cost": "cost",
            "Assembly Code": "key",
            
            # Custom parameters (commonly used)
            "Product Description": "description",
            "Product Type": "type",
            "Part Number": "model_no", 
            "Specification": "description",
            "Product URL": "url",
            "Product Image": "image_url",
            "Revit Key": "key",
            "Quantity": "qty",
            "Verification Status": "verified"
        }
        
        # Revit key generation rules
        self.key_rules = {
            "max_length": 50,
            "allowed_chars": r"[A-Za-z0-9\-_]",
            "prefixes": {
                "cabinet": "CAB",
                "faucet": "FAU", 
                "lighting": "LTG",
                "appliance": "APP",
                "fixture": "FIX",
                "hardware": "HDW",
                "flooring": "FLR",
                "tile": "TIL",
                "window": "WIN",
                "door": "DOR",
                "furniture": "FUR"
            }
        }
        
        # Revit family categories
        self.family_categories = {
            "Plumbing Fixtures": ["faucet", "sink", "toilet", "bathtub", "shower"],
            "Electrical Fixtures": ["lighting", "switch", "outlet", "fixture"],
            "Furniture": ["cabinet", "chair", "table", "furniture", "vanity"],
            "Appliances": ["appliance", "refrigerator", "oven", "dishwasher"],
            "Doors": ["door", "entry", "interior"],
            "Windows": ["window", "glazing"],
            "Flooring": ["flooring", "tile", "carpet", "hardwood"],
            "Generic Models": ["hardware", "accessory", "misc"]
        }
    
    def map_fields(self, product: Product) -> Dict[str, Any]:
        """Map product fields to Revit parameters"""
        try:
            revit_product = {}
            
            # Map standard fields
            revit_product["Type Name"] = self._clean_for_revit(product.type)
            revit_product["Type Comments"] = self._clean_for_revit(product.description)
            revit_product["Model"] = self._clean_for_revit(product.model_no or "")
            revit_product["URL"] = str(product.url) if product.url else ""
            revit_product["Type Image"] = str(product.image_url) if product.image_url else ""
            
            # Generate or use existing Revit key
            revit_product["Assembly Code"] = product.key or self.generate_revit_key(product)
            
            # Custom parameters
            revit_product["Product Description"] = self._clean_for_revit(product.description)
            revit_product["Product Type"] = self._clean_for_revit(product.type)
            revit_product["Part Number"] = self._clean_for_revit(product.model_no or "")
            revit_product["Product URL"] = str(product.url) if product.url else ""
            revit_product["Product Image"] = str(product.image_url) if product.image_url else ""
            revit_product["Quantity"] = product.qty
            revit_product["Verification Status"] = "Verified" if product.verified else "Pending"
            
            # Extract manufacturer from description if possible
            manufacturer = self._extract_manufacturer(product.description)
            if manufacturer:
                revit_product["Manufacturer"] = manufacturer
            
            # Determine family category
            category = self._determine_family_category(product.type)
            if category:
                revit_product["Family Category"] = category
            
            logger.debug(f"Mapped product {product.id} to Revit parameters")
            return revit_product
            
        except Exception as e:
            logger.error(f"Failed to map product fields for Revit: {e}")
            return {
                "Type Name": product.type or "Unknown",
                "Type Comments": "Mapping failed",
                "Assembly Code": product.key or "UNKNOWN"
            }
    
    def generate_revit_key(self, product: Product) -> str:
        """Generate Revit-compatible key for product"""
        try:
            # Get prefix based on product type
            product_type_lower = product.type.lower()
            prefix = "GEN"  # Default prefix
            
            for key_type, type_prefix in self.key_rules["prefixes"].items():
                if key_type in product_type_lower:
                    prefix = type_prefix
                    break
            
            # Create base key from model number or description
            base_key = ""
            if product.model_no:
                base_key = product.model_no
            else:
                # Extract key from description
                desc_words = product.description.split()[:3]  # First 3 words
                base_key = "_".join(desc_words)
            
            # Clean base key
            base_key = self._clean_key(base_key)
            
            # Combine prefix and base
            full_key = f"{prefix}_{base_key}"
            
            # Ensure max length
            if len(full_key) > self.key_rules["max_length"]:
                remaining_length = self.key_rules["max_length"] - len(prefix) - 1
                base_key = base_key[:remaining_length]
                full_key = f"{prefix}_{base_key}"
            
            # Ensure uniqueness by adding counter if needed
            # Note: In practice, you'd check against existing keys in project
            
            logger.debug(f"Generated Revit key: {full_key}")
            return full_key
            
        except Exception as e:
            logger.error(f"Failed to generate Revit key: {e}")
            return "UNKNOWN_KEY"
    
    def validate_revit_compatibility(self, products: List[Product]) -> List[Dict[str, Any]]:
        """Validate products for Revit compatibility"""
        try:
            issues = []
            
            for product in products:
                product_issues = []
                
                # Check key validity
                if product.key:
                    key_issues = self._validate_revit_key(product.key)
                    product_issues.extend(key_issues)
                else:
                    product_issues.append("Missing Revit key")
                
                # Check required fields
                if not product.type:
                    product_issues.append("Missing product type")
                
                if not product.description or len(product.description) < 5:
                    product_issues.append("Insufficient description")
                
                # Check field length limits
                if len(product.type) > 100:
                    product_issues.append("Product type too long for Revit")
                
                if len(product.description) > 500:
                    product_issues.append("Description too long for Revit parameter")
                
                # Check special characters
                if self._has_problematic_chars(product.type):
                    product_issues.append("Product type contains problematic characters")
                
                if self._has_problematic_chars(product.description):
                    product_issues.append("Description contains problematic characters")
                
                # Check URL validity for Revit
                if product.url and not self._is_valid_revit_url(str(product.url)):
                    product_issues.append("URL format may not work in Revit")
                
                if product_issues:
                    issues.append({
                        "product_id": product.id,
                        "product_type": product.type,
                        "product_description": product.description[:50] + "..." if len(product.description) > 50 else product.description,
                        "issues": product_issues
                    })
            
            logger.info(f"Validated {len(products)} products, found {len(issues)} with Revit compatibility issues")
            return issues
            
        except Exception as e:
            logger.error(f"Failed to validate Revit compatibility: {e}")
            return [{"error": str(e)}]
    
    def generate_import_file(self, products: List[Product], file_format: str = "csv") -> str:
        """Generate Revit-compatible import file path"""
        try:
            from datetime import datetime
            import tempfile
            import os
            
            from tools.export_tools.specbook_generator import SpecbookGenerator
            
            generator = SpecbookGenerator()
            
            if file_format.lower() == "csv":
                content = generator.generate_csv(products, template="revit")
                file_extension = "csv"
            else:
                raise ValueError(f"Unsupported import format: {file_format}")
            
            # Save to temporary file
            temp_dir = tempfile.gettempdir()
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"revit_import_{timestamp}.{file_extension}"
            file_path = os.path.join(temp_dir, filename)
            
            with open(file_path, 'wb') as f:
                f.write(content)
            
            logger.info(f"Generated Revit import file: {file_path}")
            return file_path
            
        except Exception as e:
            logger.error(f"Failed to generate Revit import file: {e}")
            raise
    
    def get_revit_import_instructions(self) -> Dict[str, Any]:
        """Get instructions for importing into Revit"""
        return {
            "preparation": [
                "Ensure all families are loaded in your Revit project",
                "Create a schedule for the appropriate category (e.g., Furniture, Plumbing Fixtures)",
                "Verify that custom parameters exist in your project template"
            ],
            "import_steps": [
                "1. Open Revit and your project file",
                "2. Go to Insert > Link > Excel or use the Schedule Properties",
                "3. Browse to the generated CSV file",
                "4. Map the CSV columns to your Revit parameters",
                "5. Verify the data imported correctly",
                "6. Apply any necessary formatting to the schedule"
            ],
            "custom_parameters": [
                "Product Description (Text)",
                "Product Type (Text)", 
                "Part Number (Text)",
                "Product URL (Text)",
                "Product Image (Text)",
                "Verification Status (Text)"
            ],
            "troubleshooting": [
                "If import fails, check for special characters in descriptions",
                "Verify that Revit keys are unique within the project",
                "Ensure URLs are properly formatted",
                "Check that product types match your loaded families"
            ]
        }
    
    def _clean_for_revit(self, text: str) -> str:
        """Clean text for Revit compatibility"""
        if not text:
            return ""
        
        # Remove problematic characters
        cleaned = re.sub(r'[<>:"/\\|?*]', '', text)
        
        # Replace multiple spaces with single space
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        
        # Limit length
        if len(cleaned) > 255:  # Revit parameter limit
            cleaned = cleaned[:252] + "..."
        
        return cleaned
    
    def _clean_key(self, key: str) -> str:
        """Clean key for Revit compatibility"""
        if not key:
            return "UNKNOWN"
        
        # Remove spaces and special chars except allowed ones
        cleaned = re.sub(r'[^A-Za-z0-9\-_]', '_', key)
        
        # Remove multiple underscores
        cleaned = re.sub(r'_+', '_', cleaned)
        
        # Remove leading/trailing underscores
        cleaned = cleaned.strip('_')
        
        return cleaned.upper()
    
    def _validate_revit_key(self, key: str) -> List[str]:
        """Validate Revit key format"""
        issues = []
        
        if not key:
            issues.append("Empty key")
            return issues
        
        if len(key) > self.key_rules["max_length"]:
            issues.append(f"Key too long (max {self.key_rules['max_length']} characters)")
        
        if not re.match(f"^{self.key_rules['allowed_chars']}+$", key):
            issues.append("Key contains invalid characters")
        
        if key.startswith('_') or key.endswith('_'):
            issues.append("Key should not start or end with underscore")
        
        return issues
    
    def _has_problematic_chars(self, text: str) -> bool:
        """Check for characters that cause issues in Revit"""
        if not text:
            return False
        
        problematic_chars = '<>:"/\\|?*'
        return any(char in text for char in problematic_chars)
    
    def _is_valid_revit_url(self, url: str) -> bool:
        """Check if URL format works well in Revit"""
        try:
            # Basic URL validation
            if not url.startswith(('http://', 'https://')):
                return False
            
            # Check for problematic characters
            if any(char in url for char in ' <>'):
                return False
            
            # Check length
            if len(url) > 500:  # Revit URL parameter limit
                return False
            
            return True
            
        except Exception:
            return False
    
    def _extract_manufacturer(self, description: str) -> Optional[str]:
        """Try to extract manufacturer from description"""
        try:
            if not description:
                return None
            
            # Common manufacturer patterns
            manufacturer_patterns = [
                r'by\s+([A-Z][a-zA-Z\s&]+?)(?:\s|$)',
                r'([A-Z][a-zA-Z\s&]+?)\s+(?:brand|company)',
                r'^([A-Z][a-zA-Z\s&]+?)\s+[A-Z]'  # Manufacturer at start
            ]
            
            for pattern in manufacturer_patterns:
                match = re.search(pattern, description)
                if match:
                    manufacturer = match.group(1).strip()
                    if 2 < len(manufacturer) < 50:  # Reasonable length
                        return manufacturer
            
            return None
            
        except Exception:
            return None
    
    def _determine_family_category(self, product_type: str) -> Optional[str]:
        """Determine Revit family category from product type"""
        try:
            if not product_type:
                return None
            
            product_type_lower = product_type.lower()
            
            for category, keywords in self.family_categories.items():
                for keyword in keywords:
                    if keyword in product_type_lower:
                        return category
            
            return "Generic Models"  # Default category
            
        except Exception:
            return None