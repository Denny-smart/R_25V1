"""
Risk Manager for Deriv R_25 Trading Bot
SIMPLIFIED VERSION - Works with Deriv's Automatic TP/SL
Focuses on: trade limits, cooldowns, and statistics tracking
risk_manager.py - PRODUCTION VERSION
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, List
import config
from utils import setup_logger, format_currency

logger = setup_logger()

class RiskManager:
    """
    Manages risk limits and trade tracking
    NOTE: TP/SL is handled automatically by Deriv API via limit_order
    """
    
    def __init__(self):
        """Initialize RiskManager with production settings"""
        self.max_trades_per_day = config.MAX_TRADES_PER_DAY
        self.max_daily_loss = config.MAX_DAILY_LOSS
        self.cooldown_seconds = config.COOLDOWN_SECONDS
        
        # Trade tracking
        self.trades_today: List[Dict] = []
        self.last_trade_time: Optional[datetime] = None
        self.daily_pnl: float = 0.0
        self.current_date = datetime.now().date()
        
        # ⭐ ACTIVE TRADE TRACKING (ONLY 1 CONCURRENT TRADE) ⭐
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
        
        # Track consecutive losses for circuit breaker
        self.consecutive_losses = 0
        self.max_consecutive_losses = 3
        
        # TP/SL amounts (for display purposes)
        self.target_profit = (config.TAKE_PROFIT_PERCENT / 100) * config.FIXED_STAKE * config.MULTIPLIER
        self.max_loss = (config.STOP_LOSS_PERCENT / 100) * config.FIXED_STAKE * config.MULTIPLIER
        
        logger.info("[OK] Risk Manager initialized (DERIV AUTO TP/SL MODE)")
        logger.info(f"   Target Profit: {format_currency(self.target_profit)} (auto-close by Deriv)")
        logger.info(f"   Max Loss: {format_currency(self.max_loss)} (auto-close by Deriv)")
        logger.info(f"   Circuit Breaker: {self.max_consecutive_losses} consecutive losses")
        logger.info(f"   Max Trades/Day: {self.max_trades_per_day}")
        logger.info(f"   Max Daily Loss: {format_currency(self.max_daily_loss)}")
    
    def reset_daily_stats(self):
        """Reset daily statistics at start of new day"""
        current_date = datetime.now().date()
        
        if current_date != self.current_date:
            logger.info(f"📅 New trading day - Resetting daily stats")
            self.current_date = current_date
            self.trades_today = []
            self.daily_pnl = 0.0
            self.last_trade_time = None
            self.active_trade = None
            self.has_active_trade = False
            self.consecutive_losses = 0
    
    def can_trade(self) -> tuple[bool, str]:
        """
        Check if trading is allowed based on risk rules
        
        Returns:
            Tuple of (can_trade: bool, reason: str)
        """
        self.reset_daily_stats()
        
        # Check if there's an active trade (ONLY 1 CONCURRENT)
        if self.has_active_trade:
            reason = "Active trade in progress (only 1 concurrent trade allowed)"
            logger.debug(f"⏸️ {reason}")
            return False, reason
        
        # Circuit breaker for consecutive losses
        if self.consecutive_losses >= self.max_consecutive_losses:
            reason = f"Circuit breaker: {self.consecutive_losses} consecutive losses"
            logger.warning(f"🛑 {reason}")
            return False, reason
        
        # Daily trade limit
        if len(self.trades_today) >= self.max_trades_per_day:
            reason = f"Daily trade limit reached ({self.max_trades_per_day} trades)"
            logger.warning(f"⚠️ {reason}")
            return False, reason
        
        # Daily loss limit
        if self.daily_pnl <= -self.max_daily_loss:
            reason = f"Daily loss limit reached ({format_currency(self.daily_pnl)})"
            logger.warning(f"⚠️ {reason}")
            return False, reason
        
        # Cooldown period
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
        
        if stake > config.FIXED_STAKE * 1.2:
            return False, f"Stake exceeds maximum ({config.FIXED_STAKE * 1.2:.2f})"
        
        # Check take profit
        if take_profit <= 0:
            return False, "Take profit must be positive"
        
        # Validate TP is close to expected $2.00
        expected_tp = (config.TAKE_PROFIT_PERCENT / 100) * stake * config.MULTIPLIER
        if abs(take_profit - expected_tp) > expected_tp * 0.3:  # 30% tolerance
            logger.warning(f"⚠️ TP {format_currency(take_profit)} differs from expected {format_currency(expected_tp)}")
        
        # Check stop loss
        if stop_loss <= 0:
            return False, "Stop loss must be positive"
        
        if stop_loss > config.MAX_LOSS_PER_TRADE * 1.15:  # 15% tolerance
            return False, f"SL {format_currency(stop_loss)} exceeds max ({format_currency(config.MAX_LOSS_PER_TRADE)})"
        
        # Check risk/reward ratio
        risk_reward_ratio = take_profit / stop_loss
        if risk_reward_ratio < 1.5:
            logger.warning(f"⚠️ Low R:R ratio: {risk_reward_ratio:.2f}")
        
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
        
        # Mark that we have an active trade
        self.active_trade = trade_record
        self.has_active_trade = True
        
        logger.info(f"📝 Trade #{self.total_trades}: {trade_info.get('direction')} @ {trade_info.get('entry_price')}")
        logger.info(f"🔒 Active trade locked (1/1 concurrent)")
        logger.info(f"   Deriv will auto-close at:")
        logger.info(f"   ✅ {format_currency(trade_record['take_profit'])} profit")
        logger.info(f"   ❌ {format_currency(trade_record['stop_loss'])} loss")
    
    def should_close_trade(self, current_pnl: float, current_price: float, 
                          previous_price: float) -> Dict:
        """
        Check if trade should be closed manually (emergency exits only)
        
        NOTE: In normal operation, Deriv handles all exits via limit_order.
        This function is only for emergency situations.
        
        Args:
            current_pnl: Current profit/loss
            current_price: Current market price
            previous_price: Previous price
        
        Returns:
            Dict with close decision (normally False)
        """
        if not self.active_trade:
            return {'should_close': False, 'reason': 'No active trade'}
        
        # Emergency exit: If daily loss limit would be exceeded
        potential_daily_loss = self.daily_pnl + current_pnl
        if potential_daily_loss <= -(self.max_daily_loss * 0.9):  # 90% of limit
            return {
                'should_close': True,
                'reason': 'emergency_daily_loss',
                'message': f'Emergency: Daily loss approaching limit ({format_currency(potential_daily_loss)})',
                'current_pnl': current_pnl
            }
        
        # Otherwise, let Deriv's limit_order handle exits
        return {'should_close': False, 'reason': 'Deriv limit_order active'}
    
    def get_exit_status(self, current_pnl: float) -> Dict:
        """
        Get current status (simplified - TP/SL handled by Deriv)
        
        Args:
            current_pnl: Current profit/loss
        
        Returns:
            Dict with status information
        """
        if not self.active_trade:
            return {'active': False}
        
        target_profit = self.active_trade.get('take_profit', 0.0)
        
        return {
            'active': True,
            'current_pnl': current_pnl,
            'target_profit': target_profit,
            'percentage_to_target': (current_pnl / target_profit * 100) if target_profit > 0 else 0,
            'consecutive_losses': self.consecutive_losses,
            'auto_tp_sl': True,  # Deriv handles TP/SL
            'deriv_managed': True
        }
    
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
            
            # Determine if it hit TP or SL
            target_profit = trade.get('take_profit', 0.0)
            max_loss = trade.get('stop_loss', 0.0)
            
            if abs(pnl - target_profit) < 0.1:
                trade['exit_type'] = 'take_profit'
                logger.info(f"🎯 Hit TAKE PROFIT target!")
            elif abs(abs(pnl) - max_loss) < 0.1:
                trade['exit_type'] = 'stop_loss'
                logger.info(f"🛑 Hit STOP LOSS limit")
            else:
                trade['exit_type'] = 'other'
        
        # Clear active trade
        if self.active_trade and self.active_trade.get('contract_id') == contract_id:
            self.active_trade = None
            self.has_active_trade = False
            logger.info(f"🔓 Trade slot unlocked (0/1 concurrent)")
        
        # Update P&L
        self.daily_pnl += pnl
        self.total_pnl += pnl
        
        # Update win/loss stats and circuit breaker
        if pnl > 0:
            self.winning_trades += 1
            self.consecutive_losses = 0  # Reset on win
            if pnl > self.largest_win:
                self.largest_win = pnl
            logger.info(f"✅ WIN | Consecutive losses reset to 0")
        elif pnl < 0:
            self.losing_trades += 1
            self.consecutive_losses += 1
            if pnl < self.largest_loss:
                self.largest_loss = pnl
            logger.warning(f"❌ LOSS | Consecutive losses: {self.consecutive_losses}/{self.max_consecutive_losses}")
        
        # Update drawdown
        if self.total_pnl > self.peak_balance:
            self.peak_balance = self.total_pnl
        
        current_drawdown = self.peak_balance - self.total_pnl
        if current_drawdown > self.max_drawdown:
            self.max_drawdown = current_drawdown
        
        logger.info(f"💰 Trade closed: {status.upper()} | P&L: {format_currency(pnl)}")
        logger.info(f"📊 Daily: {format_currency(self.daily_pnl)} | Total: {format_currency(self.total_pnl)}")
    
    def get_statistics(self) -> Dict:
        """
        Get trading statistics
        
        Returns:
            Dictionary with comprehensive statistics
        """
        win_rate = (self.winning_trades / self.total_trades * 100) if self.total_trades > 0 else 0
        
        # Count exit types
        tp_exits = sum(1 for t in self.trades_today if t.get('exit_type') == 'take_profit')
        sl_exits = sum(1 for t in self.trades_today if t.get('exit_type') == 'stop_loss')
        
        # Calculate averages
        avg_win = self.largest_win / self.winning_trades if self.winning_trades > 0 else 0
        avg_loss = abs(self.largest_loss / self.losing_trades) if self.losing_trades > 0 else 0
        
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
            'peak_balance': self.peak_balance,
            'take_profit_exits': tp_exits,
            'stop_loss_exits': sl_exits,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'consecutive_losses': self.consecutive_losses,
            'circuit_breaker_active': self.consecutive_losses >= self.max_consecutive_losses
        }
    
    def get_remaining_trades_today(self) -> int:
        """Get number of remaining trades allowed today"""
        return max(0, self.max_trades_per_day - len(self.trades_today))
    
    def get_remaining_loss_capacity(self) -> float:
        """Get remaining loss capacity for today"""
        return max(0, self.max_daily_loss + self.daily_pnl)
    
    def get_cooldown_remaining(self) -> float:
        """Get remaining cooldown time in seconds"""
        if not self.last_trade_time:
            return 0.0
        
        elapsed = (datetime.now() - self.last_trade_time).total_seconds()
        remaining = self.cooldown_seconds - elapsed
        
        return max(0.0, remaining)
    
    def print_status(self):
        """Print current risk management status"""
        can_trade, reason = self.can_trade()
        stats = self.get_statistics()
        
        print("\n" + "="*70)
        print("RISK MANAGEMENT STATUS (DERIV AUTO TP/SL)")
        print("="*70)
        print(f"Can Trade: {'✅ YES' if can_trade else '❌ NO'}")
        if not can_trade:
            print(f"Reason: {reason}")
        print(f"\nActive Trades: {1 if self.has_active_trade else 0}/1")
        if self.has_active_trade and self.active_trade:
            print(f"  └─ {self.active_trade.get('direction')} @ {self.active_trade.get('entry_price', 0):.2f}")
            print(f"  └─ Auto TP: {format_currency(self.active_trade.get('take_profit', 0))}")
            print(f"  └─ Auto SL: {format_currency(self.active_trade.get('stop_loss', 0))}")
        
        print(f"\n📊 Today's Performance:")
        print(f"  Trades: {len(self.trades_today)}/{self.max_trades_per_day}")
        print(f"  Win Rate: {stats['win_rate']:.1f}%")
        print(f"  Daily P&L: {format_currency(self.daily_pnl)}")
        print(f"  Remaining: {self.get_remaining_trades_today()} trades")
        
        print(f"\n⚡ Circuit Breaker:")
        print(f"  Consecutive Losses: {self.consecutive_losses}/{self.max_consecutive_losses}")
        if self.consecutive_losses > 0:
            print(f"  ⚠️ {self.max_consecutive_losses - self.consecutive_losses} losses until halt")
        
        print(f"\n⏱️ Cooldown: {self.get_cooldown_remaining():.0f}s remaining")
        print("="*70 + "\n")
    
    def is_within_trading_hours(self) -> bool:
        """Synthetic indices trade 24/7"""
        return True


# Testing
if __name__ == "__main__":
    print("="*70)
    print("TESTING SIMPLIFIED RISK MANAGER (DERIV AUTO TP/SL)")
    print("="*70)
    
    rm = RiskManager()
    
    print("\n✅ Configuration:")
    print(f"   Target Profit: {format_currency(rm.target_profit)}")
    print(f"   Max Loss: {format_currency(rm.max_loss)}")
    print(f"   Max Trades/Day: {rm.max_trades_per_day}")
    print(f"   Circuit Breaker: {rm.max_consecutive_losses} losses")
    
    print("\n1. Testing trade recording...")
    trade_info = {
        'contract_id': 'test_001',
        'direction': 'BUY',
        'stake': 10.0,
        'entry_price': 100.0,
        'take_profit': 2.0,
        'stop_loss': 1.0
    }
    rm.record_trade_open(trade_info)
    
    print("\n2. Testing can_trade check...")
    can_trade, reason = rm.can_trade()
    print(f"   Can trade: {can_trade}")
    print(f"   Reason: {reason}")
    
    print("\n3. Testing should_close_trade (should be False)...")
    result = rm.should_close_trade(1.50, 101.5, 101.0)
    print(f"   Should close: {result['should_close']}")
    print(f"   Reason: {result['reason']}")
    
    print("\n4. Simulating trade close with profit...")
    rm.record_trade_close('test_001', 2.0, 'won')
    
    print("\n5. Statistics:")
    stats = rm.get_statistics()
    print(f"   Total trades: {stats['total_trades']}")
    print(f"   Win rate: {stats['win_rate']:.1f}%")
    print(f"   Total P&L: {format_currency(stats['total_pnl'])}")
    print(f"   TP exits: {stats['take_profit_exits']}")
    
    print("\n" + "="*70)
    print("✅ RISK MANAGER TEST COMPLETE!")
    print("="*70)