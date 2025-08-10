
#!/usr/bin/env python3
"""
Current System Analysis Script
Analyzes the existing specbook automation pipeline performance and generates comprehensive metrics.
"""

import pandas as pd
import json
import sys
import os
from typing import Dict, List, Tuple, Any
from collections import defaultdict, Counter
import re
from pathlib import Path

# Add tools directory to path
sys.path.append(str(Path(__file__).parent / 'tools'))

from eval_product_extraction import ProductExtractionEvaluator

def analyze_scraping_performance() -> Dict[str, Any]:
    """Analyze scraping success rates and performance metrics."""
    
    print("=== SCRAPING PERFORMANCE ANALYSIS ===")
    
    # Read the results CSV
    try:
        df = pd.read_csv('01_llmpipeline/llm_results.csv')
        print(f"Total products processed: {len(df)}")
        
        # Overall success rate
        success_rate = df['success'].mean()
        print(f"Overall scrape success rate: {success_rate:.2%}")
        
        # Success rates by method
        method_success = df.groupby('final_method')['success'].agg(['count', 'mean'])
        print("\nSuccess rates by scraping method:")
        for method, stats in method_success.iterrows():
            print(f"  {method}: {stats['mean']:.2%} ({stats['count']} attempts)")
        
        # Error analysis
        errors = df[df['success'] == False]['error_reason'].value_counts()
        print(f"\nError patterns ({len(errors)} unique errors):")
        for error, count in errors.head(10).items():
            print(f"  {error}: {count} occurrences")
        
        # Content analysis
        successful_scrapes = df[df['success'] == True]
        if not successful_scrapes.empty:
            avg_content_length = successful_scrapes['content_length'].mean()
            print(f"\nContent metrics:")
            print(f"  Average content length: {avg_content_length:.0f} characters")
            print(f"  Min content length: {successful_scrapes['content_length'].min()}")
            print(f"  Max content length: {successful_scrapes['content_length'].max()}")
        
        return {
            'total_products': len(df),
            'success_rate': success_rate,
            'method_success_rates': method_success.to_dict(),
            'error_patterns': errors.to_dict(),
            'content_metrics': {
                'avg_length': avg_content_length if 'avg_content_length' in locals() else 0,
                'min_length': successful_scrapes['content_length'].min() if not successful_scrapes.empty else 0,
                'max_length': successful_scrapes['content_length'].max() if not successful_scrapes.empty else 0
            }
        }
        
    except Exception as e:
        print(f"Error analyzing scraping performance: {e}")
        return {}

def analyze_llm_extraction_quality() -> Dict[str, Any]:
    """Analyze LLM extraction quality using the existing evaluator."""
    
    print("\n=== LLM EXTRACTION QUALITY ANALYSIS ===")
    
    try:
        df = pd.read_csv('01_llmpipeline/llm_results.csv')
        
        # Filter to successful scrapes with LLM responses
        successful_extractions = df[
            (df['success'] == True) & 
            (df['llm_response'].notna()) & 
            (df['llm_response'] != '')
        ]
        
        print(f"Products with LLM responses: {len(successful_extractions)}")
        
        if successful_extractions.empty:
            print("No LLM responses found for evaluation")
            return {}
        
        # Prepare data for evaluation
        extractions = []
        for _, row in successful_extractions.iterrows():
            llm_response = row['llm_response']
            source_url = row['product_url']
            extractions.append((llm_response, source_url))
        
        # Run evaluation
        evaluator = ProductExtractionEvaluator()
        batch_results = evaluator.evaluate_batch(extractions)
        
        return batch_results
        
    except Exception as e:
        print(f"Error analyzing LLM extraction quality: {e}")
        return {}

def analyze_error_patterns() -> Dict[str, Any]:
    """Analyze error patterns and failure modes across the pipeline."""
    
    print("\n=== ERROR PATTERN ANALYSIS ===")
    
    error_analysis = {}
    
    # Check scraper logs
    try:
        log_file = Path('logs/stealth_scraper.log')
        if log_file.exists():
            with open(log_file, 'r') as f:
                log_content = f.read()
                
            # Extract error patterns
            error_patterns = re.findall(r'ERROR.*', log_content)
            warning_patterns = re.findall(r'WARNING.*', log_content)
            
            error_analysis['log_errors'] = len(error_patterns)
            error_analysis['log_warnings'] = len(warning_patterns)
            
            # Common error types
            error_types = Counter()
            for error in error_patterns:
                if 'timeout' in error.lower():
                    error_types['timeout'] += 1
                elif 'connection' in error.lower():
                    error_types['connection'] += 1
                elif 'forbidden' in error.lower() or '403' in error:
                    error_types['forbidden'] += 1
                elif 'not found' in error.lower() or '404' in error:
                    error_types['not_found'] += 1
                else:
                    error_types['other'] += 1
            
            error_analysis['error_types'] = dict(error_types)
            
            print(f"Log analysis:")
            print(f"  Total errors: {len(error_patterns)}")
            print(f"  Total warnings: {len(warning_patterns)}")
            print(f"  Error types: {dict(error_types)}")
            
    except Exception as e:
        print(f"Error analyzing log files: {e}")
        error_analysis['log_error'] = str(e)
    
    return error_analysis

def measure_pipeline_efficiency() -> Dict[str, Any]:
    """Measure overall pipeline efficiency and bottlenecks."""
    
    print("\n=== PIPELINE EFFICIENCY ANALYSIS ===")
    
    efficiency_metrics = {}
    
    try:
        df = pd.read_csv('01_llmpipeline/llm_results.csv')
        
        # Calculate processing rates
        total_products = len(df)
        successful_products = df['success'].sum()
        
        # Estimate processing time (based on rate limiting)
        # Current rate limit: 10 requests/60 seconds = 6 requests/minute
        estimated_processing_time = total_products / 6  # minutes
        
        efficiency_metrics = {
            'total_products': total_products,
            'successful_products': successful_products,
            'success_rate': successful_products / total_products if total_products > 0 else 0,
            'estimated_processing_time_minutes': estimated_processing_time,
            'estimated_processing_time_hours': estimated_processing_time / 60,
            'throughput_products_per_hour': total_products / (estimated_processing_time / 60) if estimated_processing_time > 0 else 0
        }
        
        print(f"Efficiency metrics:")
        print(f"  Total products: {total_products}")
        print(f"  Successful products: {successful_products}")
        print(f"  Success rate: {efficiency_metrics['success_rate']:.2%}")
        print(f"  Estimated processing time: {estimated_processing_time:.1f} minutes ({estimated_processing_time/60:.1f} hours)")
        print(f"  Throughput: {efficiency_metrics['throughput_products_per_hour']:.1f} products/hour")
        
        # Manual verification time analysis
        # Assuming 2-5 minutes per product for manual verification
        manual_verification_time = successful_products * 3  # average 3 minutes per product
        efficiency_metrics['manual_verification_time_minutes'] = manual_verification_time
        efficiency_metrics['manual_verification_time_hours'] = manual_verification_time / 60
        
        print(f"  Estimated manual verification time: {manual_verification_time:.0f} minutes ({manual_verification_time/60:.1f} hours)")
        
        return efficiency_metrics
        
    except Exception as e:
        print(f"Error measuring pipeline efficiency: {e}")
        return {}

def analyze_data_quality() -> Dict[str, Any]:
    """Analyze the quality of extracted data."""
    
    print("\n=== DATA QUALITY ANALYSIS ===")
    
    quality_metrics = {}
    
    try:
        df = pd.read_csv('01_llmpipeline/llm_results.csv')
        
        # Check for missing data
        missing_data = df.isnull().sum()
        print(f"Missing data counts:")
        for col, count in missing_data.items():
            if count > 0:
                print(f"  {col}: {count} missing values")
        
        # Check LLM response quality
        llm_responses = df['llm_response'].dropna()
        if not llm_responses.empty:
            # Check for valid JSON responses
            valid_json_count = 0
            for response in llm_responses:
                try:
                    json.loads(response)
                    valid_json_count += 1
                except:
                    pass
            
            json_validity_rate = valid_json_count / len(llm_responses)
            print(f"JSON validity rate: {json_validity_rate:.2%}")
            
            quality_metrics['json_validity_rate'] = json_validity_rate
            quality_metrics['total_llm_responses'] = len(llm_responses)
            quality_metrics['valid_json_responses'] = valid_json_count
        
        return quality_metrics
        
    except Exception as e:
        print(f"Error analyzing data quality: {e}")
        return {}

def generate_comprehensive_report() -> Dict[str, Any]:
    """Generate a comprehensive analysis report."""
    
    print("🔍 COMPREHENSIVE CURRENT SYSTEM ANALYSIS")
    print("=" * 50)
    
    report = {
        'timestamp': pd.Timestamp.now().isoformat(),
        'analysis_version': '1.0'
    }
    
    # Run all analyses
    report['scraping_performance'] = analyze_scraping_performance()
    report['llm_extraction_quality'] = analyze_llm_extraction_quality()
    report['error_patterns'] = analyze_error_patterns()
    report['pipeline_efficiency'] = measure_pipeline_efficiency()
    report['data_quality'] = analyze_data_quality()
    
    # Generate summary
    print("\n" + "=" * 50)
    print("📊 SUMMARY")
    print("=" * 50)
    
    if report['scraping_performance']:
        print(f"✅ Scraping Success Rate: {report['scraping_performance']['success_rate']:.1%}")
    
    if report['llm_extraction_quality']:
        print(f"✅ LLM Extraction Average Score: {report['llm_extraction_quality'].get('avg_score', 0):.3f}")
    
    if report['pipeline_efficiency']:
        print(f"⚡ Processing Throughput: {report['pipeline_efficiency'].get('throughput_products_per_hour', 0):.1f} products/hour")
    
    if report['data_quality']:
        print(f"📋 JSON Validity Rate: {report['data_quality'].get('json_validity_rate', 0):.1%}")
    
    # Save report
    report_file = Path('analysis_reports/current_system_analysis.json')
    report_file.parent.mkdir(exist_ok=True)
    
    with open(report_file, 'w') as f:
        json.dump(report, f, indent=2, default=str)
    
    print(f"\n📄 Full report saved to: {report_file}")
    
    return report

if __name__ == "__main__":
    report = generate_comprehensive_report()