"""
IntentParser - Natural language processing for architect requests
spaCy-based intent extraction with confidence scoring
"""

import re
import logging
from typing import Dict, List, Any, Tuple, Optional
from urllib.parse import urlparse
import spacy
from spacy.matcher import Matcher, PhraseMatcher

# Import models
from models.schemas import Intent, IntentAction
from config.settings import get_settings

logger = logging.getLogger(__name__)


class IntentParser:
    """Natural language parser for architect requests"""
    
    def __init__(self):
        """Initialize spaCy model and patterns"""
        self.settings = get_settings()
        self.nlp = None
        self.matcher = None
        self.phrase_matcher = None
        self._initialize_nlp()
    
    def _initialize_nlp(self):
        """Load spaCy model and setup matchers"""
        try:
            model_name = self.settings.spacy_model
            self.nlp = spacy.load(model_name)
            logger.info(f"Loaded spaCy model: {model_name}")
            
            # Initialize matchers
            self.matcher = Matcher(self.nlp.vocab)
            self.phrase_matcher = PhraseMatcher(self.nlp.vocab, attr="LOWER")
            
            # Setup intent patterns
            self._setup_intent_patterns()
            
        except OSError as e:
            logger.error(f"Failed to load spaCy model {self.settings.spacy_model}: {e}")
            logger.info("Run: python -m spacy download en_core_web_sm")
            raise
        except Exception as e:
            logger.error(f"Failed to initialize NLP: {e}")
            raise
    
    def _setup_intent_patterns(self):
        """Setup patterns for intent recognition"""
        
        # Project creation patterns
        create_project_patterns = [
            [{"LOWER": {"IN": ["create", "start", "new", "make"]}}, 
             {"LOWER": {"IN": ["project", "job", "work"]}}],
            [{"LOWER": "new"}, {"IS_ALPHA": True}, {"LOWER": "project"}],
        ]
        
        # Product addition patterns  
        add_products_patterns = [
            [{"LOWER": {"IN": ["add", "include", "process"]}}, 
             {"LOWER": {"IN": ["products", "items", "urls"]}}],
            [{"LOWER": "process"}, 
             {"LOWER": {"IN": ["these", "this"]}}],
            [{"LOWER": {"IN": ["fetch", "scrape", "get"]}}, 
             {"LOWER": {"IN": ["data", "info", "products"]}}],
        ]
        
        # Product update patterns
        update_product_patterns = [
            [{"LOWER": {"IN": ["update", "change", "modify"]}}, 
             {"LOWER": {"IN": ["product", "item"]}}],
            [{"LOWER": {"IN": ["refresh", "reload"]}}, 
             {"LOWER": {"IN": ["data", "info"]}}],
        ]
        
        # Specbook generation patterns
        generate_specbook_patterns = [
            [{"LOWER": {"IN": ["generate", "create", "make", "export"]}}, 
             {"LOWER": {"IN": ["specbook", "spec", "book", "sheet"]}}],
            [{"LOWER": "export"}, 
             {"LOWER": {"IN": ["data", "products", "csv"]}}],
        ]
        
        # List patterns
        list_patterns = [
            [{"LOWER": {"IN": ["list", "show", "display"]}}, 
             {"LOWER": {"IN": ["projects", "products", "items"]}}],
            [{"LOWER": {"IN": ["what", "which"]}}, 
             {"LOWER": {"IN": ["projects", "products"]}}],
        ]
        
        # Register patterns
        self.matcher.add("CREATE_PROJECT", create_project_patterns)
        self.matcher.add("ADD_PRODUCTS", add_products_patterns)
        self.matcher.add("UPDATE_PRODUCT", update_product_patterns)
        self.matcher.add("GENERATE_SPECBOOK", generate_specbook_patterns)
        self.matcher.add("LIST_ITEMS", list_patterns)
        
        # Project name phrases for better recognition
        project_phrases = [
            "Desert Modern", "Scottsdale Residence", "Johnson Project",
            "Kitchen Renovation", "Bathroom Remodel", "Master Bedroom"
        ]
        project_docs = [self.nlp(phrase) for phrase in project_phrases]
        self.phrase_matcher.add("PROJECT_NAMES", project_docs)
    
    def parse(self, message: str, context: Optional[Dict[str, Any]] = None) -> Intent:
        """Parse natural language message into structured intent"""
        try:
            doc = self.nlp(message.lower())
            
            # Extract entities first
            entities = self._extract_entities(message, doc)
            
            # Determine intent action
            action, confidence = self._classify_intent(doc, entities)
            
            # Apply context if available
            if context:
                entities.update(self._apply_context(entities, context))
            
            return Intent(
                action=action,
                confidence=confidence,
                entities=entities,
                raw_text=message
            )
            
        except Exception as e:
            logger.error(f"Failed to parse message '{message}': {e}")
            return Intent(
                action=IntentAction.UNKNOWN,
                confidence=0.0,
                entities={},
                raw_text=message
            )
    
    def _classify_intent(self, doc, entities: Dict[str, Any]) -> Tuple[IntentAction, float]:
        """Classify intent based on patterns and entities"""
        matches = self.matcher(doc)
        
        if not matches:
            # Fallback to keyword-based classification
            return self._fallback_classification(doc, entities)
        
        # Get the best match
        best_match = max(matches, key=lambda x: x[2] - x[1])  # Longest match
        match_id = best_match[0]
        match_label = self.nlp.vocab.strings[match_id]
        
        # Calculate confidence based on match quality
        match_length = best_match[2] - best_match[1]
        total_tokens = len(doc)
        confidence = min(0.9, (match_length / total_tokens) * 2)  # Scale confidence
        
        # Map pattern matches to actions
        action_mapping = {
            "CREATE_PROJECT": IntentAction.CREATE_PROJECT,
            "ADD_PRODUCTS": IntentAction.ADD_PRODUCTS,
            "UPDATE_PRODUCT": IntentAction.UPDATE_PRODUCT,
            "GENERATE_SPECBOOK": IntentAction.GENERATE_SPECBOOK,
            "LIST_ITEMS": self._determine_list_action(entities)
        }
        
        action = action_mapping.get(match_label, IntentAction.UNKNOWN)
        
        # Boost confidence if we have supporting entities
        if action == IntentAction.ADD_PRODUCTS and entities.get("urls"):
            confidence += 0.1
        elif action == IntentAction.CREATE_PROJECT and entities.get("project"):
            confidence += 0.1
        elif action == IntentAction.UPDATE_PRODUCT and entities.get("product_id"):
            confidence += 0.1
        
        return action, min(1.0, confidence)
    
    def _fallback_classification(self, doc, entities: Dict[str, Any]) -> Tuple[IntentAction, float]:
        """Fallback intent classification using keywords"""
        text = " ".join([token.text for token in doc])
        
        # Keyword-based classification with lower confidence
        if any(word in text for word in ["create", "new", "start", "begin"]) and \
           any(word in text for word in ["project", "job"]):
            return IntentAction.CREATE_PROJECT, 0.6
        
        elif any(word in text for word in ["add", "process", "include", "fetch"]) and \
             (entities.get("urls") or any(word in text for word in ["url", "link", "product"])):
            return IntentAction.ADD_PRODUCTS, 0.6
        
        elif any(word in text for word in ["update", "refresh", "change"]):
            return IntentAction.UPDATE_PRODUCT, 0.5
        
        elif any(word in text for word in ["generate", "export", "create"]) and \
             any(word in text for word in ["spec", "book", "sheet", "csv"]):
            return IntentAction.GENERATE_SPECBOOK, 0.6
        
        elif any(word in text for word in ["list", "show", "what", "which"]):
            return self._determine_list_action(entities), 0.5
        
        return IntentAction.UNKNOWN, 0.1
    
    def _determine_list_action(self, entities: Dict[str, Any]) -> IntentAction:
        """Determine specific list action based on entities"""
        if entities.get("project") or "project" in entities.get("object_type", ""):
            return IntentAction.LIST_PROJECTS
        else:
            return IntentAction.LIST_PRODUCTS
    
    def _extract_entities(self, message: str, doc) -> Dict[str, Any]:
        """Extract entities from the message"""
        entities = {}
        
        # Extract URLs
        urls = self._extract_urls(message)
        if urls:
            entities["urls"] = urls
        
        # Extract project names
        project_name = self._extract_project_name(message, doc)
        if project_name:
            entities["project"] = project_name
        
        # Extract numbers (could be quantities or counts)
        numbers = self._extract_numbers(doc)
        if numbers:
            entities["numbers"] = numbers
            # If we have URLs and numbers, likely indicating quantity
            if urls and len(numbers) == 1:
                entities["expected_count"] = numbers[0]
        
        # Extract product types/categories
        product_types = self._extract_product_types(doc)
        if product_types:
            entities["product_types"] = product_types
        
        # Extract time expressions
        time_expressions = self._extract_time_expressions(doc)
        if time_expressions:
            entities["deadline"] = time_expressions[0]
        
        # Extract object types (projects, products, etc.)
        object_types = self._extract_object_types(doc)
        if object_types:
            entities["object_type"] = object_types[0]
        
        return entities
    
    def _extract_urls(self, message: str) -> List[str]:
        """Extract URLs from message"""
        url_pattern = r'https?://[^\s]+'
        urls = re.findall(url_pattern, message)
        
        # Validate URLs
        valid_urls = []
        for url in urls:
            try:
                parsed = urlparse(url)
                if parsed.scheme and parsed.netloc:
                    valid_urls.append(url)
            except Exception:
                continue
        
        return valid_urls
    
    def _extract_project_name(self, message: str, doc) -> Optional[str]:
        """Extract project name from message"""
        # First try phrase matcher for known project names
        phrase_matches = self.phrase_matcher(doc)
        if phrase_matches:
            match = phrase_matches[0]
            return doc[match[1]:match[2]].text
        
        # Look for quoted project names
        quoted_pattern = r'"([^"]+)"'
        quoted_matches = re.findall(quoted_pattern, message)
        if quoted_matches:
            return quoted_matches[0]
        
        # Look for "for/called/named X" patterns
        patterns = [
            r'(?:for|called|named)\s+([A-Z][a-zA-Z\s]{2,20})',
            r'project\s+([A-Z][a-zA-Z\s]{2,20})',
            r'([A-Z][a-zA-Z\s]{2,20})\s+project'
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, message)
            if matches:
                return matches[0].strip()
        
        return None
    
    def _extract_numbers(self, doc) -> List[int]:
        """Extract numbers from the document"""
        numbers = []
        for token in doc:
            if token.like_num:
                try:
                    numbers.append(int(token.text))
                except ValueError:
                    continue
        return numbers
    
    def _extract_product_types(self, doc) -> List[str]:
        """Extract product type mentions"""
        product_keywords = [
            "kitchen", "bathroom", "appliance", "fixture", "faucet", 
            "cabinet", "countertop", "flooring", "lighting", "tile",
            "furniture", "window", "door", "hardware"
        ]
        
        found_types = []
        for token in doc:
            if token.text.lower() in product_keywords:
                found_types.append(token.text.lower())
        
        return list(set(found_types))  # Remove duplicates
    
    def _extract_time_expressions(self, doc) -> List[str]:
        """Extract time-related expressions"""
        time_keywords = ["tomorrow", "today", "asap", "urgent", "soon", "now"]
        
        found_expressions = []
        for token in doc:
            if token.text.lower() in time_keywords:
                found_expressions.append(token.text.lower())
        
        # Look for date patterns
        date_pattern = r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}'
        text = doc.text
        date_matches = re.findall(date_pattern, text)
        found_expressions.extend(date_matches)
        
        return found_expressions
    
    def _extract_object_types(self, doc) -> List[str]:
        """Extract object types being referred to"""
        object_keywords = ["projects", "products", "items", "urls", "links"]
        
        found_objects = []
        for token in doc:
            if token.text.lower() in object_keywords:
                found_objects.append(token.text.lower())
        
        return found_objects
    
    def _apply_context(self, entities: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Apply conversation context to enhance entity extraction"""
        enhanced_entities = {}
        
        # If no project specified but we have an active project
        if not entities.get("project") and context.get("active_project_name"):
            enhanced_entities["project"] = context["active_project_name"]
            enhanced_entities["project_id"] = context.get("active_project_id")
        
        # Add session context
        if context.get("session_id"):
            enhanced_entities["session_id"] = context["session_id"]
        
        return enhanced_entities
    
    def suggest_clarifications(self, intent: Intent) -> List[str]:
        """Suggest clarifying questions for ambiguous intents"""
        suggestions = []
        
        if intent.confidence < self.settings.intent_confidence_threshold:
            suggestions.append("I'm not sure what you want to do. Could you rephrase?")
        
        if intent.action == IntentAction.ADD_PRODUCTS and not intent.entities.get("urls"):
            suggestions.append("I don't see any URLs. Please provide product links to process.")
        
        if intent.action == IntentAction.CREATE_PROJECT and not intent.entities.get("project"):
            suggestions.append("What would you like to name the new project?")
        
        if intent.action == IntentAction.UPDATE_PRODUCT and not intent.entities.get("project") and not intent.entities.get("product_id"):
            suggestions.append("Which product would you like to update? Please specify the product or project.")
        
        if intent.action == IntentAction.GENERATE_SPECBOOK and not intent.entities.get("project"):
            suggestions.append("Which project should I generate the spec book for?")
        
        return suggestions