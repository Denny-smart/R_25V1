
import asyncio
import os
import sys

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from telegram_notifier import notifier

async def verify_notification():
    """Verify that the notification method runs without errors"""
    print("🚀 Starting Notification Verification...")
    
    # Mock user data
    mock_user = {
        "id": "test-user-123",
        "email": "test_user@example.com",
        "is_approved": False
    }
    
    print(f"👤 Simulating request for: {mock_user['email']}")
    
    # Temporarily disable actual sending if no credentials (to avoid crashes), 
    # but since we want to verify logic, we'll try to run it.
    # If credentials exist, it will send a real message.
    
    if not notifier.enabled:
        print("⚠️ Telegram notifier is disabled (no credentials).")
        print("   The code will still execute, but no message will be sent.")
    
    try:
        await notifier.notify_approval_request(mock_user)
        print("✅ Notification method executed successfully.")
    except Exception as e:
        print(f"❌ Error sending notification: {e}")
        sys.exit(1)

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        
    asyncio.run(verify_notification())
