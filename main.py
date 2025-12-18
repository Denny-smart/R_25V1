"""
Main Controller for Deriv R_25 Multipliers Trading Bot
Coordinates all components and runs the trading loop
main.py - COMPLETE FIXED VERSION WITH DYNAMIC CANCELLATION
"""

import asyncio
import signal
import sys
from datetime import datetime
import config
from utils import setup_logger, print_statistics, format_currency
from data_fetcher import DataFetcher
from strategy import TradingStrategy
from trade_engine import TradeEngine
from risk_manager import RiskManager

# Setup logger
logger = setup_logger(config.LOG_FILE, config.LOG_LEVEL)

# Try to import telegram notifier
try:
    from telegram_notifier import notifier
    TELEGRAM_ENABLED = True
except ImportError:
    TELEGRAM_ENABLED = False
    logger.warning("⚠️ Telegram notifier not available")

class TradingBot:
    """Main trading bot controller"""
    
    def __init__(self):
        """Initialize trading bot components"""
        self.running = False
        self.data_fetcher = None
        self.trade_engine = None
        self.strategy = None
        self.risk_manager = None
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.warning("\n⚠️ Shutdown signal received")
        self.running = False
    
    async def initialize(self) -> bool:
        """
        Initialize all bot components
        
        Returns:
            True if initialization successful
        """
        try:
            logger.info("="*60)
            logger.info("🚀 Initializing Deriv R_25 Multipliers Trading Bot")
            logger.info("="*60)
            
            # Validate configuration
            logger.info("📋 Validating configuration...")
            config.validate_config()
            logger.info("✅ Configuration valid")
            
            # Initialize components
            logger.info("🔧 Initializing components...")
            
            self.data_fetcher = DataFetcher(
                config.DERIV_API_TOKEN,
                config.DERIV_APP_ID
            )
            
            self.trade_engine = TradeEngine(
                config.DERIV_API_TOKEN,
                config.DERIV_APP_ID
            )
            
            self.strategy = TradingStrategy()
            self.risk_manager = RiskManager()
            
            # Connect to API
            logger.info("🔌 Connecting to Deriv API...")
            
            data_connected = await self.data_fetcher.connect()
            trade_connected = await self.trade_engine.connect()
            
            if not data_connected or not trade_connected:
                logger.error("❌ Failed to connect to API")
                return False
            
            # Get and log account balance
            balance = await self.data_fetcher.get_balance()
            if balance:
                logger.info(f"💰 Account Balance: {format_currency(balance)}")
                if TELEGRAM_ENABLED:
                    try:
                        await notifier.notify_bot_started(balance)
                    except Exception as e:
                        logger.error(f"❌ Telegram notification failed: {e}")
            
            # Log trading parameters
            logger.info("="*60)
            logger.info("TRADING PARAMETERS - TWO-PHASE SYSTEM")
            logger.info("="*60)
            logger.info(f"📊 Symbol: {config.SYMBOL}")
            logger.info(f"📈 Multiplier: {config.MULTIPLIER}x")
            logger.info(f"💵 Stake: {format_currency(config.FIXED_STAKE)}")
            
            if config.ENABLE_CANCELLATION:
                logger.info(f"🛡️ Cancellation: ENABLED ({config.CANCELLATION_DURATION}s)")
                logger.info(f"   Phase 2 TP: {config.POST_CANCEL_TAKE_PROFIT_PERCENT}%")
                logger.info(f"   Phase 2 SL: {config.POST_CANCEL_STOP_LOSS_PERCENT}%")
            else:
                logger.info(f"🎯 Take Profit: {config.TAKE_PROFIT_PERCENT}%")
                logger.info(f"🛑 Stop Loss: {config.STOP_LOSS_PERCENT}%")
            
            logger.info(f"⏰ Cooldown: {config.COOLDOWN_SECONDS}s")
            logger.info(f"🔢 Max Daily Trades: {config.MAX_TRADES_PER_DAY}")
            logger.info(f"💸 Max Daily Loss: {format_currency(config.MAX_DAILY_LOSS)}")
            logger.info("="*60)
            
            logger.info("✅ Bot initialized successfully!")
            return True
            
        except Exception as e:
            logger.error(f"❌ Initialization failed: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
    
    async def shutdown(self):
        """Gracefully shutdown the bot"""
        logger.info("🛑 Shutting down bot...")
        
        try:
            # Disconnect from API
            if self.data_fetcher:
                await self.data_fetcher.disconnect()
            
            if self.trade_engine:
                await self.trade_engine.disconnect()
            
            # Print final statistics
            if self.risk_manager:
                logger.info("\n" + "="*60)
                logger.info("FINAL STATISTICS")
                logger.info("="*60)
                stats = self.risk_manager.get_statistics()
                print_statistics(stats)
                
                if TELEGRAM_ENABLED:
                    try:
                        await notifier.notify_bot_stopped(stats)
                    except Exception as e:
                        logger.error(f"❌ Telegram notification failed: {e}")
            
            logger.info("✅ Bot shutdown complete")
            
        except Exception as e:
            logger.error(f"❌ Error during shutdown: {e}")
    
    async def trading_cycle(self):
        """Execute one trading cycle"""
        try:
            # Check if we can trade
            can_trade, reason = self.risk_manager.can_trade()
            
            if not can_trade:
                logger.debug(f"⏸️ Cannot trade: {reason}")
                return
            
            # Fetch market data
            logger.info("📊 Fetching market data...")
            market_data = await self.data_fetcher.fetch_multi_timeframe_data(config.SYMBOL)
            
            if '1m' not in market_data or '5m' not in market_data:
                logger.warning("⚠️ Failed to fetch complete market data")
                return
            
            data_1m = market_data['1m']
            data_5m = market_data['5m']
            
            logger.info(f"✅ Fetched {len(data_1m)} 1m candles, {len(data_5m)} 5m candles")
            
            # Analyze market
            logger.info("🔍 Analyzing market conditions...")
            signal = self.strategy.analyze(data_1m, data_5m)
            
            if not signal['can_trade']:
                logger.info(f"⚪ HOLD | Reason: {signal['details'].get('reason', 'Unknown')}")
                return
            
            # Notify signal detected
            if TELEGRAM_ENABLED:
                try:
                    await notifier.notify_signal(signal)
                except Exception as e:
                    logger.error(f"❌ Telegram notification failed: {e}")
            
            # ✅ FIXED: Validate only stake (TP/SL are calculated automatically)
            valid, msg = self.risk_manager.validate_trade_parameters(
                stake=config.FIXED_STAKE
                # TP/SL not needed - handled automatically by trade_engine
            )
            
            if not valid:
                logger.warning(f"⚠️ Invalid trade parameters: {msg}")
                return
            
            # Execute trade using the integrated execute_trade method
            logger.info(f"🚀 Executing {signal['signal']} trade...")
            
            # This single method call handles:
            # 1. Opening the trade (with dynamic cancellation fee)
            # 2. Recording it with risk manager
            # 3. Phase 1: Monitoring cancellation period
            # 4. Phase 2: Monitoring committed trade with TP/SL
            # 5. Returning final status
            result = await self.trade_engine.execute_trade(signal, self.risk_manager)
            
            if result:
                # Trade completed successfully
                pnl = result.get('profit', 0.0)
                status = result.get('status', 'unknown')
                contract_id = result.get('contract_id')
                
                # Record trade closure (opening was already recorded in execute_trade)
                self.risk_manager.record_trade_close(
                    contract_id,
                    pnl,
                    status
                )
                
                # Log statistics
                stats = self.risk_manager.get_statistics()
                logger.info(f"📈 Win Rate: {stats['win_rate']:.1f}%")
                logger.info(f"💰 Total P&L: {format_currency(stats['total_pnl'])}")
                logger.info(f"📊 Trades Today: {stats['trades_today']}/{config.MAX_TRADES_PER_DAY}")
                
                if config.ENABLE_CANCELLATION:
                    logger.info(f"🛡️ Cancelled: {stats.get('trades_cancelled', 0)}")
                    logger.info(f"✅ Committed: {stats.get('trades_committed', 0)}")
                
                # Send Telegram notification for trade result
                if TELEGRAM_ENABLED:
                    # Get the trade info from risk manager for notification
                    trade_info = None
                    for t in self.risk_manager.trades_today:
                        if t.get('contract_id') == contract_id:
                            trade_info = t
                            break
                    
                    if trade_info:
                        try:
                            await notifier.notify_trade_closed(result, trade_info)
                        except Exception as e:
                            logger.error(f"❌ Telegram notification failed: {e}")
            else:
                logger.error("❌ Trade execution failed")
            
        except Exception as e:
            logger.error(f"❌ Error in trading cycle: {e}")
            import traceback
            logger.error(traceback.format_exc())
    
    async def run(self):
        """Main trading loop"""
        try:
            # Initialize
            if not await self.initialize():
                logger.error("❌ Failed to initialize bot")
                return
            
            self.running = True
            logger.info("\n🚀 Starting main trading loop")
            logger.info("Press Ctrl+C to stop\n")
            
            cycle_count = 0
            
            # Main loop
            while self.running:
                try:
                    cycle_count += 1
                    logger.info(f"\n{'='*60}")
                    logger.info(f"CYCLE #{cycle_count} | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                    logger.info(f"{'='*60}")
                    
                    # Execute trading cycle
                    await self.trading_cycle()
                    
                    # Check cooldown
                    cooldown = self.risk_manager.get_cooldown_remaining()
                    if cooldown > 0:
                        logger.info(f"⏰ Cooldown: {cooldown:.0f}s remaining")
                    
                    # Wait before next cycle
                    wait_time = max(cooldown, 30)  # At least 30 seconds between cycles
                    logger.info(f"⏳ Next cycle in {wait_time:.0f}s...")
                    
                    # Sleep with interrupt check
                    for _ in range(int(wait_time)):
                        if not self.running:
                            break
                        await asyncio.sleep(1)
                    
                except KeyboardInterrupt:
                    logger.warning("\n⚠️ Keyboard interrupt received")
                    self.running = False
                    break
                    
                except Exception as e:
                    logger.error(f"❌ Error in main loop: {e}")
                    import traceback
                    logger.error(traceback.format_exc())
                    await asyncio.sleep(30)  # Wait before retry
            
        except Exception as e:
            logger.error(f"❌ Fatal error: {e}")
            import traceback
            logger.error(traceback.format_exc())
            
        finally:
            await self.shutdown()

def main():
    """Entry point"""
    try:
        # Print welcome banner
        print("\n" + "="*60)
        print("   DERIV R_25 MULTIPLIERS TRADING BOT")
        print("   WITH DYNAMIC CANCELLATION FEE")
        print("="*60)
        print(f"   Version: 2.0 (Two-Phase Risk)")
        print(f"   Symbol: {config.SYMBOL}")
        print(f"   Multiplier: {config.MULTIPLIER}x")
        print(f"   Cancellation: {'Enabled' if config.ENABLE_CANCELLATION else 'Disabled'}")
        print("="*60 + "\n")
        
        # Create and run bot
        bot = TradingBot()
        asyncio.run(bot.run())
        
    except KeyboardInterrupt:
        print("\n\n✅ Bot stopped by user")
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()