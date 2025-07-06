#!/usr/bin/env python3
"""
Subagent Verification Framework
Autonomous verification system with specialized agents for quality control and validation.
Extends the existing therma_pydantic.py agent framework.
"""

import json
import sys
import time
from typing import Dict, List, Any, Optional, Union, Tuple
from enum import Enum
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass

# Import the existing agent framework
from therma_pydantic import Agent, Tool, ToolParameter, Message, MessageRole, AgentConfig

# Add tools directory to path for integration
sys.path.append(str(Path(__file__).parent.parent / 'tools'))

# Import existing tools for integration
try:
    from stealth_scraper import StealthScraper, ScrapeResult
    from html_processor import HTMLProcessor, ProcessedHTML
    from eval_product_extraction import ProductExtractionEvaluator, EvalResult
except ImportError as e:
    print(f"Warning: Could not import existing tools: {e}")

class VerificationStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    VERIFIED = "verified"
    FAILED = "failed"
    ESCALATED = "escalated"

class ConfidenceLevel(str, Enum):
    HIGH = "high"      # 0.8+
    MEDIUM = "medium"  # 0.6-0.8
    LOW = "low"        # 0.4-0.6
    CRITICAL = "critical"  # <0.4

@dataclass
class VerificationResult:
    """Structured result from verification agents"""
    status: VerificationStatus
    confidence: float
    issues: List[str]
    recommendations: List[str]
    agent_id: str
    timestamp: datetime
    metadata: Dict[str, Any]

class ScrapeVerifierAgent(Agent):
    """Specialized agent for verifying web scraping results"""
    
    def __init__(self):
        config = AgentConfig(
            system_prompt="""You are a specialized scrape verification agent. Your role is to:
            1. Verify the quality and completeness of web scraping results
            2. Detect common scraping issues (blocked content, missing data)
            3. Recommend retry strategies for failed scrapes
            4. Assess content quality and relevance
            
            Always provide confidence scores and specific recommendations.""",
            max_iterations=5,
            enable_tool_calls=True
        )
        super().__init__(config=config)
        self._setup_tools()
    
    @property
    def agent_id(self) -> str:
        return "scrape_verifier"
    
    def _setup_tools(self):
        """Setup specialized verification tools"""
        
        def verify_scrape_quality(scrape_result: Dict[str, Any]) -> VerificationResult:
            """Verify the quality of a scraping result"""
            
            issues = []
            recommendations = []
            confidence = 1.0
            
            # Check for successful scrape
            if not scrape_result.get('success', False):
                issues.append("Scrape failed")
                confidence -= 0.5
                recommendations.append("Retry with different method")
            
            # Check content length
            content_length = scrape_result.get('content_length', 0)
            if content_length < 5000:
                issues.append(f"Content too short: {content_length} chars")
                confidence -= 0.2
                recommendations.append("Verify page loaded completely")
            elif content_length > 1000000:
                issues.append(f"Content unusually long: {content_length} chars")
                confidence -= 0.1
                recommendations.append("Check for infinite scroll or repeated content")
            
            # Check for error indicators
            error_reason = scrape_result.get('error_reason')
            if error_reason:
                issues.append(f"Error encountered: {error_reason}")
                if 'forbidden' in error_reason.lower() or '403' in error_reason:
                    confidence -= 0.3
                    recommendations.append("Use stealth mode or different user agent")
                elif 'timeout' in error_reason.lower():
                    confidence -= 0.2
                    recommendations.append("Increase timeout or retry during off-peak hours")
            
            # Check page issues
            page_issues = scrape_result.get('page_issues', [])
            if page_issues:
                issues.extend([f"Page issue: {issue}" for issue in page_issues])
                confidence -= len(page_issues) * 0.1
                recommendations.append("Manual review required for page issues")
            
            # Determine status
            if confidence >= 0.8:
                status = VerificationStatus.VERIFIED
            elif confidence >= 0.6:
                status = VerificationStatus.VERIFIED  # Acceptable with issues
            elif confidence >= 0.4:
                status = VerificationStatus.FAILED
                recommendations.append("Retry scraping recommended")
            else:
                status = VerificationStatus.ESCALATED
                recommendations.append("Manual intervention required")
            
            return VerificationResult(
                status=status,
                confidence=max(0.0, confidence),
                issues=issues,
                recommendations=recommendations,
                agent_id=self.agent_id,
                timestamp=datetime.now(),
                metadata={
                    'content_length': content_length,
                    'method_used': scrape_result.get('final_method'),
                    'status_code': scrape_result.get('status_code')
                }
            )
        
        def retry_failed_scrape(product_url: str, previous_method: str) -> Dict[str, str]:
            """Recommend retry strategy for failed scrapes"""
            
            strategies = {
                'requests': 'Try Selenium with stealth configuration',
                'selenium': 'Try Firecrawl or manual review',
                'firecrawl': 'Manual intervention required'
            }
            
            next_strategy = strategies.get(previous_method, 'Try different approach')
            
            return {
                'recommended_action': next_strategy,
                'priority': 'high' if previous_method == 'firecrawl' else 'medium',
                'notes': f'Previous method {previous_method} failed for {product_url}'
            }
        
        # Register tools
        verify_tool = Tool(
            name="verify_scrape_quality",
            description="Verify the quality and completeness of web scraping results",
            function=verify_scrape_quality,
            parameters=[
                ToolParameter(
                    name="scrape_result", 
                    type="object", 
                    description="Scraping result dictionary with success, content_length, etc.",
                    required=True
                )
            ]
        )
        
        retry_tool = Tool(
            name="retry_failed_scrape",
            description="Recommend retry strategy for failed scraping attempts",
            function=retry_failed_scrape,
            parameters=[
                ToolParameter(name="product_url", type="string", description="URL that failed", required=True),
                ToolParameter(name="previous_method", type="string", description="Method that failed", required=True)
            ]
        )
        
        self.add_tool(verify_tool)
        self.add_tool(retry_tool)

class ContentValidatorAgent(Agent):
    """Specialized agent for validating extracted content quality"""
    
    def __init__(self):
        config = AgentConfig(
            system_prompt="""You are a specialized content validation agent. Your role is to:
            1. Validate extracted product data for completeness and accuracy
            2. Check for data quality issues (missing fields, malformed URLs)
            3. Assess consistency between extracted fields
            4. Flag potential data anomalies
            
            Provide detailed analysis and actionable recommendations.""",
            max_iterations=5,
            enable_tool_calls=True
        )
        super().__init__(config=config)
        self._setup_tools()
    
    @property
    def agent_id(self) -> str:
        return "content_validator"
    
    def _setup_tools(self):
        """Setup content validation tools"""
        
        def validate_product_data(extraction_json: str) -> VerificationResult:
            """Validate extracted product data using existing evaluator"""
            
            try:
                # Use existing evaluation framework
                evaluator = ProductExtractionEvaluator()
                eval_result = evaluator.evaluate_extraction(extraction_json)
                
                # Convert to VerificationResult format
                status = VerificationStatus.VERIFIED if eval_result.overall_score >= 0.7 else VerificationStatus.FAILED
                if eval_result.overall_score < 0.4:
                    status = VerificationStatus.ESCALATED
                
                recommendations = []
                if not eval_result.url_valid:
                    recommendations.append("Fix invalid URLs")
                if not eval_result.required_fields_present:
                    recommendations.append("Add missing required fields")
                if eval_result.overall_score < 0.7:
                    recommendations.append("Review and improve extraction quality")
                
                return VerificationResult(
                    status=status,
                    confidence=eval_result.overall_score,
                    issues=eval_result.issues,
                    recommendations=recommendations,
                    agent_id=self.agent_id,
                    timestamp=datetime.now(),
                    metadata={
                        'field_scores': eval_result.field_quality_scores,
                        'json_parseable': eval_result.json_parseable,
                        'required_fields_present': eval_result.required_fields_present
                    }
                )
                
            except Exception as e:
                return VerificationResult(
                    status=VerificationStatus.FAILED,
                    confidence=0.0,
                    issues=[f"Validation error: {str(e)}"],
                    recommendations=["Manual review required"],
                    agent_id=self.agent_id,
                    timestamp=datetime.now(),
                    metadata={}
                )
        
        def detect_data_anomalies(batch_data: List[str]) -> Dict[str, Any]:
            """Detect anomalies across a batch of product extractions"""
            
            anomalies = {
                'duplicate_urls': [],
                'suspicious_descriptions': [],
                'inconsistent_types': [],
                'outlier_prices': []
            }
            
            parsed_data = []
            for item in batch_data:
                try:
                    parsed_data.append(json.loads(item))
                except:
                    continue
            
            if not parsed_data:
                return anomalies
            
            # Check for duplicate product URLs
            urls = [item.get('product_link', '') for item in parsed_data]
            seen_urls = set()
            for i, url in enumerate(urls):
                if url in seen_urls and url:
                    anomalies['duplicate_urls'].append({'index': i, 'url': url})
                seen_urls.add(url)
            
            # Check for suspiciously short descriptions
            for i, item in enumerate(parsed_data):
                desc = item.get('description', '')
                if len(desc) < 20 and desc.strip():
                    anomalies['suspicious_descriptions'].append({
                        'index': i, 
                        'description': desc,
                        'reason': 'Too short'
                    })
            
            # Check for inconsistent product types
            types = [item.get('type', '').lower() for item in parsed_data if item.get('type')]
            if len(set(types)) == 1 and len(types) > 5:
                anomalies['inconsistent_types'].append({
                    'reason': 'All products have same type',
                    'type': types[0] if types else 'unknown'
                })
            
            return anomalies
        
        # Register tools
        validate_tool = Tool(
            name="validate_product_data",
            description="Validate extracted product data for quality and completeness",
            function=validate_product_data,
            parameters=[
                ToolParameter(
                    name="extraction_json", 
                    type="string", 
                    description="JSON string of extracted product data",
                    required=True
                )
            ]
        )
        
        anomaly_tool = Tool(
            name="detect_data_anomalies",
            description="Detect anomalies and inconsistencies in batch data",
            function=detect_data_anomalies,
            parameters=[
                ToolParameter(
                    name="batch_data", 
                    type="array", 
                    description="Array of JSON strings to analyze",
                    required=True
                )
            ]
        )
        
        self.add_tool(validate_tool)
        self.add_tool(anomaly_tool)

class QualityAssessorAgent(Agent):
    """Specialized agent for overall quality assessment and reporting"""
    
    def __init__(self):
        config = AgentConfig(
            system_prompt="""You are a specialized quality assessment agent. Your role is to:
            1. Assess overall pipeline quality and performance
            2. Generate quality reports and recommendations
            3. Identify trends and patterns in verification results
            4. Recommend system improvements
            
            Provide comprehensive analysis and strategic recommendations.""",
            max_iterations=5,
            enable_tool_calls=True
        )
        super().__init__(config=config)
        self._setup_tools()
    
    @property
    def agent_id(self) -> str:
        return "quality_assessor"
    
    def _setup_tools(self):
        """Setup quality assessment tools"""
        
        def generate_quality_report(verification_results: List[Dict[str, Any]]) -> Dict[str, Any]:
            """Generate comprehensive quality report from verification results"""
            
            if not verification_results:
                return {"error": "No verification results provided"}
            
            total_results = len(verification_results)
            verified_count = sum(1 for r in verification_results if r.get('status') == 'verified')
            failed_count = sum(1 for r in verification_results if r.get('status') == 'failed')
            escalated_count = sum(1 for r in verification_results if r.get('status') == 'escalated')
            
            avg_confidence = sum(r.get('confidence', 0) for r in verification_results) / total_results
            
            # Analyze common issues
            all_issues = []
            for r in verification_results:
                all_issues.extend(r.get('issues', []))
            
            issue_frequency = {}
            for issue in all_issues:
                issue_frequency[issue] = issue_frequency.get(issue, 0) + 1
            
            top_issues = sorted(issue_frequency.items(), key=lambda x: x[1], reverse=True)[:5]
            
            report = {
                'summary': {
                    'total_verified': verified_count,
                    'total_failed': failed_count,
                    'total_escalated': escalated_count,
                    'success_rate': verified_count / total_results,
                    'average_confidence': avg_confidence,
                    'quality_grade': 'A' if avg_confidence >= 0.8 else 'B' if avg_confidence >= 0.6 else 'C'
                },
                'top_issues': top_issues,
                'recommendations': self._generate_recommendations(avg_confidence, top_issues, verification_results),
                'timestamp': datetime.now().isoformat()
            }
            
            return report
        
        def assess_confidence_trends(verification_history: List[Dict[str, Any]]) -> Dict[str, Any]:
            """Assess confidence trends over time"""
            
            if len(verification_history) < 2:
                return {"error": "Insufficient data for trend analysis"}
            
            # Sort by timestamp
            sorted_history = sorted(verification_history, key=lambda x: x.get('timestamp', ''))
            
            confidences = [r.get('confidence', 0) for r in sorted_history]
            
            # Calculate trend
            if len(confidences) >= 5:
                recent_avg = sum(confidences[-5:]) / 5
                earlier_avg = sum(confidences[:-5]) / len(confidences[:-5])
                trend = "improving" if recent_avg > earlier_avg else "declining"
            else:
                trend = "insufficient_data"
            
            return {
                'trend': trend,
                'current_confidence': confidences[-1],
                'average_confidence': sum(confidences) / len(confidences),
                'confidence_range': {
                    'min': min(confidences),
                    'max': max(confidences)
                }
            }
        
        # Register tools
        report_tool = Tool(
            name="generate_quality_report",
            description="Generate comprehensive quality report from verification results",
            function=generate_quality_report,
            parameters=[
                ToolParameter(
                    name="verification_results", 
                    type="array", 
                    description="Array of verification result objects",
                    required=True
                )
            ]
        )
        
        trend_tool = Tool(
            name="assess_confidence_trends",
            description="Assess confidence and quality trends over time",
            function=assess_confidence_trends,
            parameters=[
                ToolParameter(
                    name="verification_history", 
                    type="array", 
                    description="Historical verification results",
                    required=True
                )
            ]
        )
        
        self.add_tool(report_tool)
        self.add_tool(trend_tool)
    
    def _generate_recommendations(self, avg_confidence: float, top_issues: List[Tuple[str, int]], 
                                verification_results: List[Dict[str, Any]]) -> List[str]:
        """Generate strategic recommendations based on analysis"""
        
        recommendations = []
        
        if avg_confidence < 0.6:
            recommendations.append("Critical: Implement immediate quality improvements")
        elif avg_confidence < 0.8:
            recommendations.append("Moderate: Focus on addressing common issues")
        
        # Issue-specific recommendations
        for issue, count in top_issues[:3]:
            if 'content too short' in issue.lower():
                recommendations.append("Improve scraping timeouts and page load detection")
            elif 'missing required fields' in issue.lower():
                recommendations.append("Enhance LLM prompts for better field extraction")
            elif 'invalid url' in issue.lower():
                recommendations.append("Implement URL validation and cleaning")
        
        # Performance recommendations
        escalated_count = sum(1 for r in verification_results if r.get('status') == 'escalated')
        if escalated_count > len(verification_results) * 0.1:
            recommendations.append("High escalation rate: Review automated validation criteria")
        
        return recommendations

class VerificationCoordinator:
    """Coordinates multiple verification agents and manages workflows"""
    
    def __init__(self):
        self.scrape_verifier = ScrapeVerifierAgent()
        self.content_validator = ContentValidatorAgent()
        self.quality_assessor = QualityAssessorAgent()
        self.verification_history: List[VerificationResult] = []
    
    def verify_product_extraction(self, scrape_result: Dict[str, Any], 
                                extracted_data: str) -> Dict[str, VerificationResult]:
        """Complete verification workflow for a single product extraction"""
        
        results = {}
        
        # Step 1: Verify scraping quality
        print(f"🔍 Verifying scrape quality...")
        scrape_verification = self.scrape_verifier.tools['verify_scrape_quality'].call(
            scrape_result=scrape_result
        )
        results['scrape_verification'] = scrape_verification
        
        # Step 2: Validate extracted content (only if scrape was successful)
        if scrape_verification.status in [VerificationStatus.VERIFIED]:
            print(f"📋 Validating extracted content...")
            content_verification = self.content_validator.tools['validate_product_data'].call(
                extraction_json=extracted_data
            )
            results['content_verification'] = content_verification
        else:
            print(f"⚠️  Skipping content validation due to scrape issues")
        
        # Store results in history
        for result in results.values():
            self.verification_history.append(result)
        
        return results
    
    def verify_batch(self, product_batch: List[Tuple[Dict[str, Any], str]]) -> Dict[str, Any]:
        """Verify a batch of product extractions"""
        
        print(f"🚀 Starting batch verification for {len(product_batch)} products...")
        
        batch_results = []
        
        for i, (scrape_result, extracted_data) in enumerate(product_batch):
            print(f"Processing product {i+1}/{len(product_batch)}")
            
            product_results = self.verify_product_extraction(scrape_result, extracted_data)
            batch_results.append(product_results)
        
        # Generate quality assessment
        print(f"📊 Generating quality assessment...")
        verification_data = []
        for product_results in batch_results:
            for result in product_results.values():
                verification_data.append({
                    'status': result.status.value,
                    'confidence': result.confidence,
                    'issues': result.issues,
                    'agent_id': result.agent_id,
                    'timestamp': result.timestamp.isoformat()
                })
        
        quality_report = self.quality_assessor.tools['generate_quality_report'].call(
            verification_results=verification_data
        )
        
        return {
            'individual_results': batch_results,
            'quality_report': quality_report,
            'batch_summary': {
                'total_products': len(product_batch),
                'verification_timestamp': datetime.now().isoformat()
            }
        }
    
    def get_escalated_cases(self) -> List[VerificationResult]:
        """Get all cases that require manual intervention"""
        
        return [result for result in self.verification_history 
                if result.status == VerificationStatus.ESCALATED]
    
    def export_verification_report(self, output_path: str = None) -> str:
        """Export comprehensive verification report"""
        
        if not output_path:
            output_path = f"verification_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        report = {
            'report_metadata': {
                'generated_at': datetime.now().isoformat(),
                'total_verifications': len(self.verification_history),
                'agents_used': ['scrape_verifier', 'content_validator', 'quality_assessor']
            },
            'verification_history': [
                {
                    'status': result.status.value,
                    'confidence': result.confidence,
                    'issues': result.issues,
                    'recommendations': result.recommendations,
                    'agent_id': result.agent_id,
                    'timestamp': result.timestamp.isoformat(),
                    'metadata': result.metadata
                }
                for result in self.verification_history
            ],
            'escalated_cases': [
                {
                    'confidence': result.confidence,
                    'issues': result.issues,
                    'recommendations': result.recommendations,
                    'timestamp': result.timestamp.isoformat()
                }
                for result in self.get_escalated_cases()
            ]
        }
        
        # Save report
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f"📄 Verification report exported to: {output_file}")
        return str(output_file)

# Example usage and testing
def test_verification_framework():
    """Test the verification framework with sample data"""
    
    print("🧪 TESTING VERIFICATION FRAMEWORK")
    print("=" * 50)
    
    # Create coordinator
    coordinator = VerificationCoordinator()
    
    # Sample test data
    sample_scrape_result = {
        'success': True,
        'content_length': 45000,
        'final_method': 'requests',
        'status_code': 200,
        'page_issues': []
    }
    
    sample_extraction = json.dumps({
        'image_url': 'https://example.com/product.jpg',
        'product_link': 'https://example.com/product',
        'type': 'Furniture',
        'description': 'A high-quality modern chair with ergonomic design',
        'model_no': 'CH-2024',
        'qty': '1'
    })
    
    # Test single product verification
    print("Testing single product verification...")
    results = coordinator.verify_product_extraction(sample_scrape_result, sample_extraction)
    
    for verification_type, result in results.items():
        print(f"{verification_type}: {result.status.value} (confidence: {result.confidence:.2f})")
        if result.issues:
            print(f"  Issues: {result.issues}")
        if result.recommendations:
            print(f"  Recommendations: {result.recommendations}")
    
    # Export test report
    report_path = coordinator.export_verification_report("test_reports/verification_test.json")
    
    print(f"\n✅ Verification framework test completed!")
    print(f"📊 Test report: {report_path}")

if __name__ == "__main__":
    test_verification_framework()