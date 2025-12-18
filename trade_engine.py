"""
Trade Engine for Deriv R_25 Trading Bot
Handles trade execution and monitoring - FIXED WITH PROPER LIMIT_ORDER
trade_engine.py
"""

import asyncio
import websockets
import json
from datetime import datetime
from typing import Dict, Optional, Any
import config
from utils import setup_logger, format_currency, get_status_emoji

# Setup logger first
logger = setup_logger()

# Import telegram notifier with proper error handling
try:
    from telegram_notifier import notifier
    logger.info("✅ Telegram notifier loaded")
except ImportError as e:
    logger.warning(f"⚠️ Telegram notifier not available: {e}")
    notifier = None
except Exception as e:
    logger.error(f"❌ Error loading Telegram notifier: {e}")
    notifier = None

class TradeEngine:
    """Handles all trade execution operations"""
    
    def __init__(self, api_token: str, app_id: str = "1089"):
        """
        Initialize TradeEngine
        
        Args:
            api_token: Deriv API token
            app_id: Deriv app ID
        """
        self.api_token = api_token
        self.app_id = app_id
        self.ws_url = f"{config.WS_URL}?app_id={app_id}"
        self.ws = None
        self.is_connected = False
        self.active_contract_id = None
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 5
        
        # ⭐ Calculate TP/SL amounts (DOLLAR AMOUNTS, NOT PERCENTAGES) ⭐
        self.take_profit_amount = self._calculate_tp_amount()
        self.stop_loss_amount = self._calculate_sl_amount()
        
        logger.info(f"🎯 TP/SL calculated:")
        logger.info(f"   Take Profit: {format_currency(self.take_profit_amount)}")
        logger.info(f"   Stop Loss: {format_currency(self.stop_loss_amount)}")
    
    def _calculate_tp_amount(self) -> float:
        """
        Calculate Take Profit in dollar amount
        TP Amount = (TP% / 100) × Stake × Multiplier
        """
        tp_amount = (config.TAKE_PROFIT_PERCENT / 100) * config.FIXED_STAKE * config.MULTIPLIER
        return round(tp_amount, 2)
    
    def _calculate_sl_amount(self) -> float:
        """
        Calculate Stop Loss in dollar amount
        SL Amount = (SL% / 100) × Stake × Multiplier
        """
        sl_amount = (config.STOP_LOSS_PERCENT / 100) * config.FIXED_STAKE * config.MULTIPLIER
        return round(sl_amount, 2)
    
    async def connect(self) -> bool:
        """
        Connect to Deriv WebSocket API
        
        Returns:
            True if connected successfully
        """
        try:
            self.ws = await websockets.connect(
                self.ws_url,
                ping_interval=30,
                ping_timeout=10
            )
            self.is_connected = True
            self.reconnect_attempts = 0
            logger.info("✅ Trade Engine connected to Deriv API")
            
            # Authorize
            await self.authorize()
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to connect Trade Engine: {e}")
            self.is_connected = False
            return False
    
    async def reconnect(self) -> bool:
        """
        Attempt to reconnect to the API
        
        Returns:
            True if reconnected successfully
        """
        self.reconnect_attempts += 1
        
        if self.reconnect_attempts > self.max_reconnect_attempts:
            logger.error(f"❌ Max reconnection attempts reached")
            return False
        
        logger.warning(f"⚠️ Reconnecting... (attempt {self.reconnect_attempts}/{self.max_reconnect_attempts})")
        
        if self.ws:
            try:
                await self.ws.close()
            except:
                pass
        
        self.is_connected = False
        await asyncio.sleep(min(2 ** self.reconnect_attempts, 30))
        
        return await self.connect()
    
    async def ensure_connected(self) -> bool:
        """Ensure WebSocket is connected"""
        if not self.is_connected or not self.ws or self.ws.closed:
            return await self.reconnect()
        return True
    
    async def disconnect(self):
        """Disconnect from WebSocket"""
        if self.ws:
            await self.ws.close()
            self.is_connected = False
            logger.info("🔌 Trade Engine disconnected")
    
    async def authorize(self) -> bool:
        """
        Authorize connection with API token
        
        Returns:
            True if authorized successfully
        """
        try:
            auth_request = {"authorize": self.api_token}
            await self.ws.send(json.dumps(auth_request))
            response = await self.ws.recv()
            data = json.loads(response)
            
            if "error" in data:
                logger.error(f"❌ Authorization failed: {data['error']['message']}")
                return False
            
            if "authorize" in data:
                logger.info("✅ Trade Engine authorized")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"❌ Authorization error: {e}")
            return False
    
    async def send_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Send request to API and get response
        
        Args:
            request: Request dictionary
        
        Returns:
            Response dictionary
        """
        try:
            if not await self.ensure_connected():
                return {"error": {"message": "Failed to establish connection"}}
            
            await self.ws.send(json.dumps(request))
            response = await self.ws.recv()
            return json.loads(response)
            
        except (websockets.exceptions.ConnectionClosed, 
                websockets.exceptions.ConnectionClosedError) as e:
            logger.warning(f"⚠️ Connection closed: {e}")
            if await self.reconnect():
                try:
                    await self.ws.send(json.dumps(request))
                    response = await self.ws.recv()
                    return json.loads(response)
                except Exception as retry_error:
                    return {"error": {"message": str(retry_error)}}
            return {"error": {"message": "Connection lost"}}
            
        except Exception as e:
            logger.error(f"❌ Request error: {e}")
            return {"error": {"message": str(e)}}
    
    async def open_trade(self, direction: str, stake: float, 
                        take_profit_percent: float, stop_loss_percent: float) -> Optional[Dict]:
        """
        Open a multiplier trade with PROPER limit_order format
        
        Args:
            direction: 'UP' or 'DOWN' or 'BUY' or 'SELL'
            stake: Stake amount
            take_profit_percent: Take profit as percentage (for logging only)
            stop_loss_percent: Stop loss as percentage (for logging only)
        
        Returns:
            Trade information dictionary or None if failed
        """
        try:
            # Map signal direction to contract type
            if direction.upper() in ['UP', 'BUY']:
                contract_type = config.CONTRACT_TYPE  # MULTUP
            else:
                contract_type = config.CONTRACT_TYPE_DOWN  # MULTDOWN
            
            # ⭐ CRITICAL FIX: Use DOLLAR AMOUNTS in limit_order ⭐
            buy_request = {
                "buy": 1,
                "price": stake,
                "parameters": {
                    "amount": stake,
                    "amount_type": "stake",
                    "basis": "stake",
                    "contract_type": contract_type,
                    "currency": "USD",
                    "multiplier": config.MULTIPLIER,
                    "symbol": config.SYMBOL,
                    "limit_order": {  # ⭐ THIS IS THE KEY FIX ⭐
                        "take_profit": self.take_profit_amount,  # Dollar amount, not percentage!
                        "stop_loss": self.stop_loss_amount       # Dollar amount, not percentage!
                    }
                }
            }
            
            logger.info(f"📤 Sending {direction} trade request...")
            logger.info(f"   Contract Type: {contract_type}")
            logger.info(f"   Stake: {format_currency(stake)}")
            logger.info(f"   Multiplier: {config.MULTIPLIER}x")
            logger.info(f"   TP Amount: {format_currency(self.take_profit_amount)} (target: $2.00)")
            logger.info(f"   SL Amount: {format_currency(self.stop_loss_amount)} (max loss: $1.00)")
            
            response = await self.send_request(buy_request)
            
            if "error" in response:
                error_msg = response['error'].get('message', 'Unknown error')
                error_details = response['error'].get('details', {})
                logger.error(f"❌ Trade failed: {error_msg}")
                if error_details:
                    logger.error(f"   Details: {error_details}")
                return None
            
            if "buy" not in response:
                logger.error("❌ Invalid trade response")
                return None
            
            # Extract trade information
            buy_info = response["buy"]
            contract_id = buy_info["contract_id"]
            entry_price = float(buy_info.get("buy_price", stake))
            longcode = buy_info.get("longcode", "")
            
            self.active_contract_id = contract_id
            
            trade_info = {
                'contract_id': contract_id,
                'direction': direction,
                'stake': stake,
                'entry_price': entry_price,
                'take_profit': self.take_profit_amount,  # Store dollar amount
                'stop_loss': self.stop_loss_amount,      # Store dollar amount
                'take_profit_percent': take_profit_percent,
                'stop_loss_percent': stop_loss_percent,
                'multiplier': config.MULTIPLIER,
                'contract_type': contract_type,
                'open_time': datetime.now(),
                'status': 'open',
                'longcode': longcode
            }
            
            logger.info(f"✅ Trade opened successfully!")
            logger.info(f"   Contract ID: {contract_id}")
            logger.info(f"   Entry Price: {entry_price:.2f}")
            logger.info(f"   Direction: {direction} ({contract_type})")
            logger.info(f"   TP will trigger at: {format_currency(self.take_profit_amount)} profit")
            logger.info(f"   SL will trigger at: {format_currency(self.stop_loss_amount)} loss")
            
            # Send Telegram notification
            if notifier is not None:
                try:
                    await notifier.notify_trade_opened(trade_info)
                except Exception as e:
                    logger.error(f"❌ Telegram notification failed: {e}")
            
            return trade_info
            
        except Exception as e:
            logger.error(f"❌ Error opening trade: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None
    
    async def close_trade(self, contract_id: str) -> Optional[Dict]:
        """
        Close an active trade
        
        Args:
            contract_id: Contract ID to close
        
        Returns:
            Close information dictionary or None if failed
        """
        try:
            sell_request = {
                "sell": contract_id,
                "price": 0  # Close at market price
            }
            
            logger.info(f"📤 Closing trade {contract_id}...")
            
            response = await self.send_request(sell_request)
            
            if "error" in response:
                logger.error(f"❌ Failed to close trade: {response['error']['message']}")
                return None
            
            if "sell" not in response:
                logger.error("❌ Invalid close response")
                return None
            
            sell_info = response["sell"]
            sold_for = float(sell_info.get("sold_for", 0))
            
            close_info = {
                'contract_id': contract_id,
                'sold_for': sold_for,
                'close_time': datetime.now()
            }
            
            logger.info(f"✅ Trade closed | Sold for: {format_currency(sold_for)}")
            
            self.active_contract_id = None
            return close_info
            
        except Exception as e:
            logger.error(f"❌ Error closing trade: {e}")
            return None
    
    async def get_trade_status(self, contract_id: str) -> Optional[Dict]:
        """
        Get current status of a trade
        
        Args:
            contract_id: Contract ID
        
        Returns:
            Trade status dictionary or None if failed
        """
        try:
            proposal_request = {
                "proposal_open_contract": 1,
                "contract_id": contract_id
            }
            
            response = await self.send_request(proposal_request)
            
            if "error" in response:
                logger.error(f"❌ Failed to get trade status: {response['error']['message']}")
                return None
            
            if "proposal_open_contract" not in response:
                return None
            
            contract = response["proposal_open_contract"]
            
            # Extract status with fallback
            trade_status = contract.get('status', None)
            is_sold = contract.get('is_sold', 0) == 1
            profit = float(contract.get('profit', 0))
            
            # Determine status from profit if status is None/unknown
            if trade_status is None or trade_status == '' or trade_status == 'unknown':
                if is_sold:
                    # Trade is closed, determine win/loss from P&L
                    if profit > 0:
                        trade_status = 'won'
                        logger.debug(f"Status derived: WON (profit: {profit})")
                    elif profit < 0:
                        trade_status = 'lost'
                        logger.debug(f"Status derived: LOST (profit: {profit})")
                    else:
                        trade_status = 'sold'
                        logger.debug(f"Status derived: SOLD (profit: {profit})")
                else:
                    # Trade still open
                    trade_status = 'open'
            
            status_info = {
                'contract_id': contract_id,
                'status': trade_status,
                'current_price': float(contract.get('current_spot', 0)),
                'entry_price': float(contract.get('entry_spot', 0)),
                'profit': profit,
                'bid_price': float(contract.get('bid_price', 0)),
                'buy_price': float(contract.get('buy_price', 0)),
                'is_sold': is_sold
            }
            
            return status_info
            
        except Exception as e:
            logger.error(f"❌ Error getting trade status: {e}")
            return None
    
    async def monitor_trade(self, contract_id: str, trade_info: Dict,
                          max_duration: int = 3600, risk_manager=None) -> Optional[Dict]:
        """
        Monitor an active trade until it closes
        NOTE: With proper limit_order, Deriv handles TP/SL automatically!
        
        Args:
            contract_id: Contract ID to monitor
            trade_info: Original trade information (for notifications)
            max_duration: Maximum duration in seconds
            risk_manager: RiskManager instance (for early exits beyond TP/SL)
        
        Returns:
            Final trade result dictionary
        """
        try:
            start_time = datetime.now()
            monitor_interval = config.MONITOR_INTERVAL
            last_status_log = datetime.now()
            status_log_interval = 30  # Log status every 30 seconds
            
            previous_price = trade_info.get('entry_price', 0.0)
            
            logger.info(f"👁️ Monitoring trade {contract_id}...")
            logger.info(f"   ⚡ Deriv will auto-close at TP: {format_currency(self.take_profit_amount)} or SL: {format_currency(self.stop_loss_amount)}")
            
            while True:
                # Check if max duration exceeded
                elapsed = (datetime.now() - start_time).total_seconds()
                if elapsed > max_duration:
                    logger.warning(f"⏰ Max duration reached, closing trade...")
                    close_info = await self.close_trade(contract_id)
                    if close_info:
                        status = await self.get_trade_status(contract_id)
                        if status and notifier is not None:
                            try:
                                await notifier.notify_trade_closed(status, trade_info)
                            except Exception as e:
                                logger.error(f"❌ Close notification failed: {e}")
                        return status
                    return None
                
                # Get current status
                status = await self.get_trade_status(contract_id)
                
                if not status:
                    logger.error("❌ Failed to get trade status")
                    await asyncio.sleep(monitor_interval)
                    continue
                
                # ⭐ OPTIONAL: Check additional dynamic exit conditions beyond TP/SL ⭐
                if risk_manager is not None:
                    current_pnl = status['profit']
                    current_price = status['current_price']
                    
                    exit_check = risk_manager.should_close_trade(
                        current_pnl, 
                        current_price, 
                        previous_price
                    )
                    
                    if exit_check['should_close']:
                        logger.info(f"🎯 {exit_check['message']}")
                        # Force close the trade
                        await self.close_trade(contract_id)
                        # Get final status
                        await asyncio.sleep(2)  # Wait for close to process
                        final_status = await self.get_trade_status(contract_id)
                        if final_status:
                            if notifier is not None:
                                try:
                                    await notifier.notify_trade_closed(final_status, trade_info)
                                except Exception as e:
                                    logger.error(f"❌ Close notification failed: {e}")
                            return final_status
                    
                    # Update previous price for next iteration
                    previous_price = current_price
                
                # Check if trade is closed (by TP/SL or otherwise)
                if status['is_sold'] or status['status'] in ['sold', 'won', 'lost']:
                    trade_status = status.get('status', 'closed')
                    final_pnl = status.get('profit', 0)
                    
                    # If status is still unclear, derive from P&L
                    if trade_status in [None, '', 'unknown', 'closed']:
                        if final_pnl > 0:
                            trade_status = 'won'
                        elif final_pnl < 0:
                            trade_status = 'lost'
                        else:
                            trade_status = 'sold'
                    
                    emoji = get_status_emoji(trade_status)
                    
                    # ⭐ Log whether it hit TP or SL ⭐
                    if abs(final_pnl - self.take_profit_amount) < 0.1:
                        logger.info(f"🎯 {emoji} Trade hit TAKE PROFIT target!")
                    elif abs(abs(final_pnl) - self.stop_loss_amount) < 0.1:
                        logger.info(f"🛑 {emoji} Trade hit STOP LOSS!")
                    else:
                        logger.info(f"{emoji} Trade closed | Status: {trade_status.upper()}")
                    
                    logger.info(f"   Final P&L: {format_currency(status['profit'])}")
                    
                    # Send Telegram notification for trade close
                    if notifier is not None:
                        try:
                            await notifier.notify_trade_closed(status, trade_info)
                        except Exception as e:
                            logger.error(f"❌ Close notification failed: {e}")
                    
                    return status
                
                # Log current P&L periodically
                current_pnl = status['profit']
                current_price = status['current_price']
                
                # Log detailed status every 30 seconds
                time_since_last_log = (datetime.now() - last_status_log).total_seconds()
                if time_since_last_log >= status_log_interval:
                    pnl_emoji = "📈" if current_pnl >= 0 else "📉"
                    log_msg = f"{pnl_emoji} P&L: {format_currency(current_pnl)} | Price: {current_price:.2f} | {int(elapsed)}s"
                    
                    # Show progress to target
                    pnl_to_target_pct = (current_pnl / self.take_profit_amount * 100) if self.take_profit_amount > 0 else 0
                    if pnl_to_target_pct > 0:
                        log_msg += f" | {pnl_to_target_pct:.0f}% to TP"
                    
                    logger.info(log_msg)
                    last_status_log = datetime.now()
                
                # Wait before next check
                await asyncio.sleep(monitor_interval)
                
        except Exception as e:
            logger.error(f"❌ Error monitoring trade: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None
    
    async def execute_trade(self, signal: Dict, risk_manager) -> Optional[Dict]:
        """
        Execute complete trade cycle: open, monitor, close
        
        Args:
            signal: Trading signal dictionary
            risk_manager: RiskManager instance to record trades
        
        Returns:
            Final trade result or None if failed
        """
        try:
            direction = signal['signal']
            
            # Open trade with proper limit_order
            trade_info = await self.open_trade(
                direction=direction,
                stake=config.FIXED_STAKE,
                take_profit_percent=config.TAKE_PROFIT_PERCENT,
                stop_loss_percent=config.STOP_LOSS_PERCENT
            )
            
            if not trade_info:
                return None
            
            # Record trade opening with risk manager
            risk_manager.record_trade_open(trade_info)
            
            # Monitor trade until it closes
            final_status = await self.monitor_trade(
                trade_info['contract_id'],
                trade_info,
                max_duration=config.MAX_TRADE_DURATION,
                risk_manager=risk_manager
            )
            
            # CRITICAL: If monitoring failed, unlock the trade slot
            if final_status is None:
                logger.error("❌ Monitoring failed - unlocking trade slot")
                risk_manager.has_active_trade = False
                risk_manager.active_trade = None
            
            return final_status
            
        except Exception as e:
            logger.error(f"❌ Error executing trade: {e}")
            import traceback
            logger.error(traceback.format_exc())
            
            # CRITICAL: Unlock trade slot on any error
            try:
                risk_manager.has_active_trade = False
                risk_manager.active_trade = None
                logger.info("🔓 Trade slot unlocked after error")
            except:
                pass
            
            return None