
import sys
import os
import asyncio
import logging
from unittest.mock import MagicMock

# Add root to path
sys.path.append(os.getcwd())

from app.core.context import user_id_var
from app.core.logging import setup_api_logger
from app.bot.events import event_manager

async def test_logging():
    print("🧪 Starting Log Verification...")
    
    # 1. Setup Logger
    # Clear existing handlers
    root = logging.getLogger()
    if root.handlers:
        root.handlers = []
        
    setup_api_logger()
    
    # 2. Mock Event Manager Broadcast
    # We need strictly async mock
    broadcast_calls = []
    
    async def mock_broadcast(msg):
        broadcast_calls.append(msg)
        print(f"📡 Broadcast captured: {msg['account_id']} | {msg['message']}")
    
    event_manager.broadcast = MagicMock(side_effect=mock_broadcast)
    
    # 3. Test Case 1: System Log (No User)
    print("\n[Case 1] Logging without user context...")
    logging.info("System startup message")
    await asyncio.sleep(0.1) # Yield to event loop
    
    if len(broadcast_calls) == 0:
        print("✅ PASS: System log was NOT broadcasted")
    else:
        print(f"❌ FAIL: System log broadcasted! {broadcast_calls}")
        sys.exit(1)
        
    # 4. Test Case 2: User Log
    print("\n[Case 2] Logging WITH user context...")
    user_id = "user_test_123"
    token = user_id_var.set(user_id)
    
    try:
        logging.info("User specific action detected")
    finally:
        user_id_var.reset(token)
        
    await asyncio.sleep(0.1) # Yield to event loop
    
    if len(broadcast_calls) == 1:
        log = broadcast_calls[0]
        if log['account_id'] == user_id and "User specific action" in log['message']:
            print("✅ PASS: User log broadcasted with correct ID")
        else:
            print(f"❌ FAIL: Incorrect log content. Got: {log}")
            sys.exit(1)
    else:
        print(f"❌ FAIL: Log not broadcasted. Calls: {len(broadcast_calls)}")
        sys.exit(1)

    print("\n🎉 All verification tests passed!")

if __name__ == "__main__":
    asyncio.run(test_logging())
