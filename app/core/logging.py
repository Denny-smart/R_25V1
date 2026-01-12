import logging
import sys
import asyncio
from typing import Optional

from app.core.context import user_id_var
from app.bot.events import event_manager

class ContextInjectingFilter(logging.Filter):
    """
    Injects user_id from contextvars into the log record.
    """
    def filter(self, record):
        record.user_id = user_id_var.get()
        return True

class WebSocketLoggingHandler(logging.Handler):
    """
    Broadcasts logs to the specific user via WebSocket.
    """
    def emit(self, record):
        try:
            user_id = getattr(record, 'user_id', None)
            if not user_id:
                return

            msg = self.format(record)
            
            # Broadcast directly using event manager
            # We use create_task because emit is synchronous
            try:
                loop = asyncio.get_running_loop()
                if loop.is_running():
                    payload = {
                        "type": "log",
                        "level": record.levelname,
                        "message": msg,
                        "timestamp": record.created,
                        "account_id": user_id
                    }
                    loop.create_task(event_manager.broadcast(payload))
            except RuntimeError:
                # No running loop (e.g. startup/shutdown or different thread)
                pass
                
        except Exception:
            self.handleError(record)

def setup_api_logger():
    """Setup logging for FastAPI application"""
    
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    
    # 1. Console Handler (Standard Output)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    
    formatter = logging.Formatter(
        '%(asctime)s | %(levelname)s | %(name)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # 2. Context Filter (Injects user_id)
    context_filter = ContextInjectingFilter()
    logger.addFilter(context_filter)
    
    # 3. WebSocket Handler (Streams to Frontend)
    ws_handler = WebSocketLoggingHandler()
    ws_handler.setLevel(logging.INFO)
    ws_handler.setFormatter(formatter)
    logger.addHandler(ws_handler)
    
    return logger