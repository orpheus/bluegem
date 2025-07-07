#!/usr/bin/env python3
"""
Test async database operations
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent))

async def test_async_database():
    """Test async database operations"""
    try:
        from models.database import DatabaseManager
        from config.settings import get_settings
        
        settings = get_settings()
        print(f"Database URL: {settings.database_url}")
        
        db_manager = DatabaseManager(settings.database_url)
        
        # Test async session
        async with db_manager.async_session() as session:
            from sqlalchemy import text
            result = await session.execute(text("SELECT current_database()"))
            db_name = result.scalar()
            print(f"✅ Connected to database: {db_name}")
        
        await db_manager.close()
        print("✅ Async database operations working correctly")
        return True
        
    except Exception as e:
        print(f"❌ Async database test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_project_store():
    """Test ProjectStore initialization"""
    try:
        from tools.data_management.project_store import ProjectStore
        
        store = ProjectStore()
        print("✅ ProjectStore initialized successfully")
        
        # Test initialization method
        await store.initialize()
        print("✅ ProjectStore.initialize() completed")
        
        await store.db_manager.close()
        return True
        
    except Exception as e:
        print(f"❌ ProjectStore test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Run async database tests"""
    print("🔧 Testing Async Database Operations...\n")
    
    tests = [
        ("Async Database Connection", test_async_database()),
        ("ProjectStore Initialization", test_project_store()),
    ]
    
    results = []
    for test_name, test_coro in tests:
        print(f"Running {test_name}...")
        try:
            result = await test_coro
            results.append(result)
        except Exception as e:
            print(f"❌ {test_name} failed with exception: {e}")
            results.append(False)
        print()
    
    # Summary
    passed = sum(results)
    total = len(results)
    
    print(f"📊 Async Test Results: {passed}/{total} passed")
    
    if passed == total:
        print("🎉 All async database tests passed!")
        print("The agentic framework is ready for async operations.")
    else:
        print("❌ Some async tests failed.")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())