import logging
from typing import Dict, List, Optional
from app.core.supabase import supabase

logger = logging.getLogger(__name__)

class UserTradesService:
    """
    Service to handle persistence of user trades to Supabase.
    """

    @staticmethod
    def save_trade(user_id: str, trade_data: Dict) -> Optional[Dict]:
        """
        Save a completed trade to Supabase.
        """
        try:
            # Prepare record
            record = {
                "user_id": user_id,
                "contract_id": str(trade_data.get("contract_id")),
                "symbol": trade_data.get("symbol"),
                "signal": trade_data.get("signal"),
                "stake": trade_data.get("stake"),
                "entry_price": trade_data.get("entry_price"),
                "exit_price": trade_data.get("exit_price"),
                "profit": trade_data.get("profit"),
                "status": trade_data.get("status"),
                "timestamp": trade_data.get("timestamp") or trade_data.get("closed_at")
            }

            # Insert into Supabase
            response = supabase.table("trades").insert(record).execute()
            
            if response.data:
                logger.info(f"✅ Trade persisted to DB: {record['contract_id']}")
                return response.data[0]
            else:
                logger.error("Failed to persist trade: No data returned")
                return None
                
        except Exception as e:
            logger.error(f"❌ Error saving trade to DB: {e}")
            return None

    @staticmethod
    def get_user_trades(user_id: str, limit: int = 50) -> List[Dict]:
        """
        Fetch trade history for a user from Supabase.
        """
        try:
            response = supabase.table("trades")\
                .select("*")\
                .eq("user_id", user_id)\
                .order("timestamp", desc=True)\
                .limit(limit)\
                .execute()
            
            return response.data if response.data else []
            
        except Exception as e:
            logger.error(f"❌ Error fetching trade history: {e}")
            return []
