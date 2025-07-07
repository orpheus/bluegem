#!/usr/bin/env python3
"""
Simple test script to verify the agentic framework setup
"""

import asyncio
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent))

def test_database_connection():
    """Test database connectivity"""
    try:
        import psycopg2
        
        # Test with synchronous driver first
        conn = psycopg2.connect(
            host="127.0.0.1",
            port=5432,
            user="postgres", 
            password="password",
            database="bluegem"
        )
        
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        result = cursor.fetchone()[0]
        assert result == 1
        
        cursor.close()
        conn.close()
        
        print("✅ Database connection successful")
        return True
        
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return False

def test_redis_connection():
    """Test Redis connectivity"""
    try:
        import redis
        
        r = redis.Redis(host='localhost', port=6379, decode_responses=True)
        r.ping()
        print("✅ Redis connection successful")
        return True
        
    except Exception as e:
        print(f"❌ Redis connection failed: {e}")
        return False

def test_pydantic_models():
    """Test Pydantic model validation"""
    try:
        from models.schemas import Project, Product, IntentAction
        
        # Test Project model
        project = Project(name="Test Project")
        assert project.name == "Test Project"
        assert project.status.value == "draft"
        
        # Test Product model
        product = Product(
            project_id="test_project",
            url="https://example.com/product",
            type="Test Product",
            description="A test product",
            qty=1
        )
        assert product.qty == 1
        assert product.confidence_score == 0.0
        
        print("✅ Pydantic models validation successful")
        return True
        
    except Exception as e:
        print(f"❌ Pydantic models failed: {e}")
        return False

def test_spacy_model():
    """Test spaCy NLP model"""
    try:
        import spacy
        
        # Load the model
        nlp = spacy.load("en_core_web_sm")
        
        # Test basic processing
        doc = nlp("Create a new project called Test Project")
        assert len(doc) > 0
        
        print("✅ spaCy NLP model loaded successfully")
        return True
        
    except Exception as e:
        print(f"❌ spaCy model failed: {e}")
        return False

def test_openai_key():
    """Test OpenAI API key is configured"""
    try:
        openai_key = os.getenv("OPENAI_API_KEY")
        if not openai_key or openai_key == "your-openai-key-here":
            print("⚠️  OpenAI API key not configured (this is optional for testing)")
            return True
        
        print("✅ OpenAI API key is configured")
        return True
        
    except Exception as e:
        print(f"❌ OpenAI configuration failed: {e}")
        return False

async def main():
    """Run all tests"""
    print("🚀 Testing Agentic Specbook Framework Setup...\n")
    
    tests = [
        ("Database Connection", test_database_connection),
        ("Redis Connection", test_redis_connection),
        ("Pydantic Models", test_pydantic_models),
        ("spaCy NLP Model", test_spacy_model),
        ("OpenAI Configuration", test_openai_key),
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"Running {test_name}...")
        try:
            if asyncio.iscoroutine(test_func):
                result = await test_func
            else:
                result = test_func()
            results.append(result)
        except Exception as e:
            print(f"❌ {test_name} failed with exception: {e}")
            results.append(False)
        print()
    
    # Summary
    passed = sum(results)
    total = len(results)
    
    print(f"📊 Test Results: {passed}/{total} passed")
    
    if passed == total:
        print("🎉 All tests passed! The agentic framework is ready to use.")
        print("\nNext steps:")
        print("1. Set your OpenAI API key: export OPENAI_API_KEY='your-key'")
        print("2. Run the chat interface: python -m cli.chat_interface")
    else:
        print("❌ Some tests failed. Please check the setup steps.")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())