"""
Risk Manager for Deriv R_25 Trading Bot
Manages trading limits, cooldowns, and risk parameters
risk_manager.py - WITH 1 CONCURRENT TRADE LIMIT
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, List
import config
from utils import setup_logger, format_currency

logger = setup_logger()

class RiskManager:
    """Manages all risk-related operations"""
    
    def __init__(self):
        """Initialize RiskManager with default settings"""
        self.max_trades_per_day = config.MAX_TRADES_PER_DAY
        self.max_daily_loss = config.MAX_DAILY_LOSS
        self.cooldown_seconds = config.COOLDOWN_SECONDS
        
        # Trade tracking
        self.trades_today: List[Dict] = []
        self.last_trade_time: Optional[datetime] = None
        self.daily_pnl: float = 0.0
        self.current_date = datetime.now().date()
        
        # ⭐ ACTIVE TRADE TRACKING (ONLY 1 CONCURRENT TRADE ALLOWED) ⭐
        self.active_trade: Optional[Dict] = None
        self.has_active_trade = False
        
        # Statistics
        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0
        self.total_pnl = 0.0
        self.largest_win = 0.0
        self.largest_loss = 0.0
        self.max_drawdown = 0.0
        self.peak_balance = 0.0
        
        logger.info("[OK] Risk Manager initialized (Max concurrent trades: 1)")
    
    def reset_daily_stats(self):
        """Reset daily statistics at start of new day"""
        current_date = datetime.now().date()
        
        if current_date != self.current_date:
            logger.info(f"📅 New trading day - Resetting daily stats")
            self.current_date = current_date
            self.trades_today = []
            self.daily_pnl = 0.0
            self.last_trade_time = None
            
            # Clear active trade tracking for new day
            self.active_trade = None
            self.has_active_trade = False
    
    def can_trade(self) -> tuple[bool, str]:
        """
        Check if trading is allowed based on risk rules
        
        Returns:
            Tuple of (can_trade: bool, reason: str)
        """
        # Reset stats if new day
        self.reset_daily_stats()
        
        # ⭐ CRITICAL: Check if there's an active trade (ONLY 1 CONCURRENT TRADE) ⭐
        if self.has_active_trade:
            reason = "Active trade in progress (only 1 concurrent trade allowed)"
            logger.debug(f"⏸️ {reason}")
            return False, reason
        
        # Check daily trade limit
        if len(self.trades_today) >= self.max_trades_per_day:
            reason = f"Daily trade limit reached ({self.max_trades_per_day} trades)"
            logger.warning(f"⚠️ {reason}")
            return False, reason
        
        # Check daily loss limit
        if self.daily_pnl <= -self.max_daily_loss:
            reason = f"Daily loss limit reached ({format_currency(self.daily_pnl)})"
            logger.warning(f"⚠️ {reason}")
            return False, reason
        
        # Check cooldown period
        if self.last_trade_time:
            time_since_last = (datetime.now() - self.last_trade_time).total_seconds()
            if time_since_last < self.cooldown_seconds:
                remaining = self.cooldown_seconds - time_since_last
                reason = f"Cooldown active ({remaining:.0f}s remaining)"
                return False, reason
        
        return True, "OK"
    
    def validate_trade_parameters(self, stake: float, take_profit: float, 
                                  stop_loss: float) -> tuple[bool, str]:
        """
        Validate trade parameters against risk rules
        
        Args:
            stake: Trade stake amount
            take_profit: Take profit amount
            stop_loss: Stop loss amount
        
        Returns:
            Tuple of (is_valid: bool, message: str)
        """
        # Check stake
        if stake <= 0:
            return False, "Stake must be positive"
        
        if stake > config.FIXED_STAKE * 2:
            return False, f"Stake exceeds maximum ({config.FIXED_STAKE * 2})"
        
        # Check take profit
        if take_profit <= 0:
            return False, "Take profit must be positive"
        
        # Check stop loss
        if stop_loss <= 0:
            return False, "Stop loss must be positive"
        
        if stop_loss > config.MAX_LOSS_PER_TRADE:
            return False, f"Stop loss exceeds maximum ({config.MAX_LOSS_PER_TRADE})"
        
        # Check risk/reward ratio (optional)
        risk_reward_ratio = take_profit / stop_loss
        if risk_reward_ratio < 0.5:
            logger.warning(f"⚠️ Low risk/reward ratio: {risk_reward_ratio:.2f}")
        
        return True, "Valid"
    
    def record_trade_open(self, trade_info: Dict):
        """
        Record a new trade opening
        
        Args:
            trade_info: Dictionary with trade information
        """
        trade_record = {
            'timestamp': datetime.now(),
            'contract_id': trade_info.get('contract_id'),
            'direction': trade_info.get('direction'),
            'stake': trade_info.get('stake', 0.0),
            'entry_price': trade_info.get('entry_price', 0.0),
            'take_profit': trade_info.get('take_profit', 0.0),
            'stop_loss': trade_info.get('stop_loss', 0.0),
            'status': 'open'
        }
        
        self.trades_today.append(trade_record)
        self.last_trade_time = datetime.now()
        self.total_trades += 1
        
        # ⭐ Mark that we have an active trade (ONLY 1 CONCURRENT) ⭐
        self.active_trade = trade_record
        self.has_active_trade = True
        
        logger.info(f"📝 Trade recorded: {trade_info.get('direction')} @ {trade_info.get('entry_price')}")
        logger.info(f"🔒 Active trade locked (1/1 concurrent trades)")
    
    def record_trade_close(self, contract_id: str, pnl: float, status: str):
        """
        Record trade closure and update statistics
        
        Args:
            contract_id: Contract ID
            pnl: Profit/loss amount
            status: Trade status ('won', 'lost', 'sold')
        """
        # Find trade in today's list
        trade = None
        for t in self.trades_today:
            if t.get('contract_id') == contract_id:
                trade = t
                break
        
        if trade:
            trade['status'] = status
            trade['pnl'] = pnl
            trade['close_time'] = datetime.now()
        
        # ⭐ Clear active trade (ALLOW NEW TRADES) ⭐
        if self.active_trade and self.active_trade.get('contract_id') == contract_id:
            self.active_trade = None
            self.has_active_trade = False
            logger.info(f"🔓 Trade slot unlocked (0/1 concurrent trades)")
        
        # Update P&L
        self.daily_pnl += pnl
        self.total_pnl += pnl
        
        # Update win/loss stats
        if pnl > 0:
            self.winning_trades += 1
            if pnl > self.largest_win:
                self.largest_win = pnl
        elif pnl < 0:
            self.losing_trades += 1
            if pnl < self.largest_loss:
                self.largest_loss = pnl
        
        # Update drawdown
        if self.total_pnl > self.peak_balance:
            self.peak_balance = self.total_pnl
        
        current_drawdown = self.peak_balance - self.total_pnl
        if current_drawdown > self.max_drawdown:
            self.max_drawdown = current_drawdown
        
        logger.info(f"💰 Trade closed: {status.upper()} | P&L: {format_currency(pnl)}")
        logger.info(f"📊 Daily P&L: {format_currency(self.daily_pnl)} | Total: {format_currency(self.total_pnl)}")
    
    def get_statistics(self) -> Dict:
        """
        Get trading statistics
        
        Returns:
            Dictionary with statistics
        """
        win_rate = (self.winning_trades / self.total_trades * 100) if self.total_trades > 0 else 0
        
        return {
            'total_trades': self.total_trades,
            'winning_trades': self.winning_trades,
            'losing_trades': self.losing_trades,
            'win_rate': win_rate,
            'total_pnl': self.total_pnl,
            'daily_pnl': self.daily_pnl,
            'trades_today': len(self.trades_today),
            'largest_win': self.largest_win,
            'largest_loss': self.largest_loss,
            'max_drawdown': self.max_drawdown,
            'peak_balance': self.peak_balance
        }
    
    def get_remaining_trades_today(self) -> int:
        """Get number of remaining trades allowed today"""
        return max(0, self.max_trades_per_day - len(self.trades_today))
    
    def get_remaining_loss_capacity(self) -> float:
        """Get remaining loss capacity for today"""
        return max(0, self.max_daily_loss + self.daily_pnl)
    
    def get_cooldown_remaining(self) -> float:
        """
        Get remaining cooldown time in seconds
        
        Returns:
            Seconds remaining (0 if no cooldown)
        """
        if not self.last_trade_time:
            return 0.0
        
        elapsed = (datetime.now() - self.last_trade_time).total_seconds()
        remaining = self.cooldown_seconds - elapsed
        
        return max(0.0, remaining)
    
    def print_status(self):
        """Print current risk management status"""
        can_trade, reason = self.can_trade()
        
        print("\n" + "="*60)
        print("RISK MANAGEMENT STATUS")
        print("="*60)
        print(f"Can Trade: {'✅ YES' if can_trade else '❌ NO'}")
        if not can_trade:
            print(f"Reason: {reason}")
        print(f"Active Trades: {1 if self.has_active_trade else 0}/1")
        if self.has_active_trade and self.active_trade:
            print(f"  └─ {self.active_trade.get('direction')} @ {self.active_trade.get('entry_price', 0):.2f}")
        print(f"Trades Today: {len(self.trades_today)}/{self.max_trades_per_day}")
        print(f"Daily P&L: {format_currency(self.daily_pnl)}")
        print(f"Cooldown: {self.get_cooldown_remaining():.0f}s remaining")
        print("="*60 + "\n")
    
    def is_within_trading_hours(self) -> bool:
        """
        Check if within trading hours (synthetic indices trade 24/7)
        
        Returns:
            True (always for synthetic indices)
        """
        return True

# Testing
if __name__ == "__main__":
    print("Testing Risk Manager...")
    
    # Create risk manager
    rm = RiskManager()
    
    # Test 1: Check if can trade
    print("\n1. Testing initial trading permission...")
    can_trade, reason = rm.can_trade()
    print(f"Can trade: {can_trade} - {reason}")
    
    # Test 2: Validate trade parameters
    print("\n2. Testing trade parameter validation...")
    valid, msg = rm.validate_trade_parameters(10.0, 3.0, 5.0)
    print(f"Valid parameters: {valid} - {msg}")
    
    # Test 3: Test concurrent trade limit
    print("\n3. Testing concurrent trade limit...")
    trade_info = {
        'contract_id': 'test_001',
        'direction': 'BUY',
        'stake': 10.0,
        'entry_price': 100.0,
        'take_profit': 3.0,
        'stop_loss': 5.0
    }
    
    # Open first trade
    rm.record_trade_open(trade_info)
    print(f"Active trades: {1 if rm.has_active_trade else 0}/1")
    
    # Try to open second trade (should be blocked)
    can_trade_2, reason_2 = rm.can_trade()
    print(f"Can open second trade: {can_trade_2} - {reason_2}")
    
    # Close the trade
    rm.record_trade_close('test_001', 3.0, 'won')
    print(f"Active trades after close: {1 if rm.has_active_trade else 0}/1")
    
    # Now should be able to trade again
    can_trade_3, reason_3 = rm.can_trade()
    print(f"Can trade after close: {can_trade_3} - {reason_3}")
    
    # Test 4: Get statistics
    print("\n4. Testing statistics...")
    stats = rm.get_statistics()
    for key, value in stats.items():
        print(f"{key}: {value}")
    
    # Test 5: Print status
    print("\n5. Testing status print...")
    rm.print_status()
    
    print("\n✅ Risk Manager test complete!")