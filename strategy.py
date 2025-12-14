"""
Trading Strategy for Deriv R_25 Trading Bot
Multi-timeframe strategy with strict entry/exit rules
strategy.py - ENHANCED WITH ANTI-REVERSAL CONFIRMATIONS
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional, Tuple
import config
from indicators import (
    calculate_all_indicators,
    is_bullish_candle,
    is_bearish_candle,
    get_candle_body,
    get_candle_range
)
from utils import setup_logger, get_signal_emoji

logger = setup_logger()

class TradingStrategy:
    """Implements the multi-timeframe trading strategy with enhanced entry confirmations"""
    
    def __init__(self):
        """Initialize strategy with configuration parameters"""
        self.rsi_buy_threshold = config.RSI_BUY_THRESHOLD
        self.rsi_sell_threshold = config.RSI_SELL_THRESHOLD
        self.adx_threshold = config.ADX_THRESHOLD
        self.minimum_signal_score = config.MINIMUM_SIGNAL_SCORE
        
        # ⭐ NEW: Anti-reversal settings ⭐
        self.max_wick_ratio = 0.65  # Reject candles with >65% wick
        self.min_body_ratio = 0.25  # Require at least 25% body
        self.require_price_stability = True  # Check last 3 candles for stability
        self.min_consecutive_candles = 2  # Minimum candles in same direction
        
        logger.info("[OK] Trading Strategy initialized (Enhanced with anti-reversal)")
    
    def analyze(self, data_1m: pd.DataFrame, data_5m: pd.DataFrame) -> Dict:
        """
        Analyze market data and generate trading signal
        
        Args:
            data_1m: 1-minute candle data
            data_5m: 5-minute candle data
        
        Returns:
            Dictionary with signal, direction, score, and details
        """
        try:
            # Validate data amounts
            min_raw_1m = int(config.CANDLES_1M * 0.8)
            min_raw_5m = int(config.CANDLES_5M * 0.8)
            
            if len(data_1m) < min_raw_1m:
                return self._create_hold_signal(f"Not enough 1m data ({len(data_1m)}/{min_raw_1m} candles)")
            
            if len(data_5m) < min_raw_5m:
                return self._create_hold_signal(f"Not enough 5m data ({len(data_5m)}/{min_raw_5m} candles)")
            
            # Calculate indicators
            df_1m = calculate_all_indicators(data_1m.copy())
            df_5m = calculate_all_indicators(data_5m.copy())
            
            # Drop NaN rows
            df_1m = df_1m.dropna()
            df_5m = df_5m.dropna()
            
            # Validate post-calculation data
            min_after_indicators = 10
            
            if len(df_1m) < min_after_indicators:
                return self._create_hold_signal("Insufficient 1m data after calculations")
            
            if len(df_5m) < min_after_indicators:
                return self._create_hold_signal("Insufficient 5m data after calculations")
            
            # Get latest values
            latest_1m = df_1m.iloc[-1]
            latest_5m = df_5m.iloc[-1]
            
            # Check for NaN in critical indicators
            critical_indicators = ['atr', 'rsi', 'adx', 'sma_100', 'ema_20']
            for ind in critical_indicators:
                if pd.isna(latest_1m[ind]):
                    return self._create_hold_signal(f"Invalid 1m {ind}")
                if pd.isna(latest_5m[ind]):
                    return self._create_hold_signal(f"Invalid 5m {ind}")
            
            # Step 1: Validate ATR ranges
            if not self._validate_atr(latest_1m, latest_5m):
                return self._create_hold_signal("ATR out of range")
            
            # Step 2: Check for volatility spike
            if self._is_volatility_spike(df_1m):
                return self._create_hold_signal("Volatility spike detected")
            
            # Step 3: Check for weak candle
            if self._is_weak_candle(df_1m):
                return self._create_hold_signal("Weak candle detected")
            
            # ⭐ NEW Step 4: Check candle quality (anti-reversal) ⭐
            candle_check = self._check_candle_quality(df_1m)
            if not candle_check['is_quality']:
                return self._create_hold_signal(f"Poor candle: {candle_check['reason']}")
            
            # ⭐ NEW Step 5: Check price stability (anti-reversal) ⭐
            if self.require_price_stability:
                stability_check = self._check_price_stability(df_1m)
                if not stability_check['is_stable']:
                    return self._create_hold_signal(f"Price unstable: {stability_check['reason']}")
            
            # Step 6: Evaluate BUY signal
            buy_score, buy_details = self._evaluate_buy_signal(df_1m, df_5m)
            
            # Step 7: Evaluate SELL signal
            sell_score, sell_details = self._evaluate_sell_signal(df_1m, df_5m)
            
            # ⭐ NEW Step 8: Apply momentum confirmation bonus ⭐
            buy_score, buy_details = self._apply_momentum_bonus(df_1m, buy_score, buy_details, 'BUY')
            sell_score, sell_details = self._apply_momentum_bonus(df_1m, sell_score, sell_details, 'SELL')
            
            # Step 9: Determine final signal
            signal_result = self._determine_signal(buy_score, sell_score, 
                                                   buy_details, sell_details)
            
            return signal_result
            
        except Exception as e:
            logger.error(f"[ERROR] Error in strategy analysis: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return self._create_hold_signal(f"Analysis error: {e}")
    
    def _validate_atr(self, latest_1m: pd.Series, latest_5m: pd.Series) -> bool:
        """Validate ATR is within acceptable ranges"""
        atr_1m = latest_1m['atr']
        atr_5m = latest_5m['atr']
        
        logger.info(f"   📊 ATR Check - 1m: {atr_1m:.4f} (range: {config.ATR_MIN_1M}-{config.ATR_MAX_1M})")
        logger.info(f"   📊 ATR Check - 5m: {atr_5m:.4f} (range: {config.ATR_MIN_5M}-{config.ATR_MAX_5M})")
        
        if not (config.ATR_MIN_1M <= atr_1m <= config.ATR_MAX_1M):
            logger.info(f"   ❌ 1m ATR REJECTED: {atr_1m:.4f} is outside valid range")
            return False
        
        if not (config.ATR_MIN_5M <= atr_5m <= config.ATR_MAX_5M):
            logger.info(f"   ❌ 5m ATR REJECTED: {atr_5m:.4f} is outside valid range")
            return False
        
        logger.info(f"   ✅ ATR validation passed")
        return True
    
    def _is_volatility_spike(self, df_1m: pd.DataFrame) -> bool:
        """Check if there's a volatility spike"""
        if len(df_1m) < 2:
            return False
            
        prev_candle = df_1m.iloc[-2]
        prev_range = prev_candle['high'] - prev_candle['low']
        atr = prev_candle['atr']
        
        if pd.isna(prev_range) or pd.isna(atr):
            return False
        
        spike_threshold = atr * config.VOLATILITY_SPIKE_MULTIPLIER
        
        if prev_range > spike_threshold:
            logger.debug(f"Volatility spike: range {prev_range:.4f} > threshold {spike_threshold:.4f}")
            return True
        
        return False
    
    def _is_weak_candle(self, df_1m: pd.DataFrame) -> bool:
        """Check if last candle is too weak"""
        if len(df_1m) < 1:
            return False
            
        last_candle = df_1m.iloc[-1]
        body = abs(last_candle['close'] - last_candle['open'])
        atr = last_candle['atr']
        
        if pd.isna(body) or pd.isna(atr):
            return False
        
        weak_threshold = atr * config.WEAK_CANDLE_MULTIPLIER
        
        if body < weak_threshold:
            logger.debug(f"Weak candle: body {body:.4f} < threshold {weak_threshold:.4f}")
            return True
        
        return False
    
    def _check_candle_quality(self, df_1m: pd.DataFrame) -> Dict:
        """
        ⭐ NEW: Check if last candle shows conviction (not indecision) ⭐
        Prevents entering on candles with long wicks (reversal signals)
        
        Returns:
            Dict with quality assessment
        """
        if len(df_1m) < 1:
            return {'is_quality': False, 'reason': 'No data'}
        
        last_candle = df_1m.iloc[-1]
        
        # Calculate candle metrics
        body = abs(last_candle['close'] - last_candle['open'])
        total_range = last_candle['high'] - last_candle['low']
        
        # Avoid division by zero
        if total_range == 0 or body == 0:
            return {'is_quality': False, 'reason': 'Zero range/body candle'}
        
        # Calculate ratios
        body_ratio = body / total_range
        wick_ratio = (total_range - body) / total_range
        
        # Upper and lower wicks
        if last_candle['close'] >= last_candle['open']:  # Bullish
            upper_wick = last_candle['high'] - last_candle['close']
            lower_wick = last_candle['open'] - last_candle['low']
        else:  # Bearish
            upper_wick = last_candle['high'] - last_candle['open']
            lower_wick = last_candle['close'] - last_candle['low']
        
        # Quality checks
        # 1. Too much wick = indecision/rejection
        if wick_ratio > self.max_wick_ratio:
            return {
                'is_quality': False,
                'reason': f'High wick ratio {wick_ratio:.2f} (max {self.max_wick_ratio})',
                'wick_ratio': wick_ratio,
                'body_ratio': body_ratio
            }
        
        # 2. Too small body = indecision
        if body_ratio < self.min_body_ratio:
            return {
                'is_quality': False,
                'reason': f'Small body ratio {body_ratio:.2f} (min {self.min_body_ratio})',
                'wick_ratio': wick_ratio,
                'body_ratio': body_ratio
            }
        
        # 3. Long upper wick on bullish candle = rejection at top
        if last_candle['close'] > last_candle['open']:  # Bullish
            if upper_wick > body * 1.5:  # Upper wick is 1.5x body
                return {
                    'is_quality': False,
                    'reason': 'Long upper wick (rejection)',
                    'wick_ratio': wick_ratio,
                    'body_ratio': body_ratio
                }
        
        # 4. Long lower wick on bearish candle = rejection at bottom
        if last_candle['close'] < last_candle['open']:  # Bearish
            if lower_wick > body * 1.5:
                return {
                    'is_quality': False,
                    'reason': 'Long lower wick (rejection)',
                    'wick_ratio': wick_ratio,
                    'body_ratio': body_ratio
                }
        
        return {
            'is_quality': True,
            'reason': 'Quality candle',
            'wick_ratio': wick_ratio,
            'body_ratio': body_ratio
        }
    
    def _check_price_stability(self, df_1m: pd.DataFrame) -> Dict:
        """
        ⭐ NEW: Check if price is stable (not erratic) ⭐
        Prevents entering during choppy, directionless movement
        
        Returns:
            Dict with stability assessment
        """
        lookback = 5  # Check last 5 candles
        
        if len(df_1m) < lookback:
            return {'is_stable': False, 'reason': 'Insufficient data'}
        
        recent = df_1m.tail(lookback)
        closes = recent['close'].values
        
        # Check for consistent direction
        # Count how many times price changed direction
        direction_changes = 0
        for i in range(1, len(closes) - 1):
            prev_move = closes[i] - closes[i-1]
            curr_move = closes[i+1] - closes[i]
            
            # Direction change if signs differ and moves are significant
            if prev_move * curr_move < 0:  # Opposite signs
                direction_changes += 1
        
        # Too many direction changes = choppy
        if direction_changes > 2:
            return {
                'is_stable': False,
                'reason': f'Too choppy ({direction_changes} direction changes)',
                'direction_changes': direction_changes
            }
        
        # Check for extreme volatility in recent candles
        ranges = (recent['high'] - recent['low']).values
        avg_range = np.mean(ranges)
        max_range = np.max(ranges)
        
        # If any candle is 3x average range = instability
        if max_range > avg_range * 3:
            return {
                'is_stable': False,
                'reason': 'Extreme range volatility',
                'direction_changes': direction_changes
            }
        
        return {
            'is_stable': True,
            'reason': 'Price stable',
            'direction_changes': direction_changes
        }
    
    def _apply_momentum_bonus(self, df_1m: pd.DataFrame, score: int, 
                            details: Dict, direction: str) -> Tuple[int, Dict]:
        """
        ⭐ NEW: Apply bonus points for strong momentum continuation ⭐
        Rewards trades that show consistent directional movement
        
        Args:
            df_1m: 1-minute data
            score: Current score
            details: Current details
            direction: 'BUY' or 'SELL'
        
        Returns:
            Updated score and details
        """
        if len(df_1m) < self.min_consecutive_candles:
            return score, details
        
        # Check last N candles
        recent = df_1m.tail(self.min_consecutive_candles + 1)
        
        if direction == 'BUY':
            # Count consecutive bullish candles
            bullish_count = sum(
                recent.iloc[i]['close'] > recent.iloc[i]['open'] 
                for i in range(len(recent))
            )
            
            # Check for higher lows (uptrend structure)
            lows = recent['low'].values
            higher_lows = all(lows[i] >= lows[i-1] for i in range(1, len(lows)))
            
            if bullish_count >= self.min_consecutive_candles:
                score += 1
                details['consecutive_momentum'] = True
                details['bullish_candles'] = bullish_count
                logger.debug(f"   ✅ Momentum bonus: {bullish_count} bullish candles")
            
            if higher_lows:
                score += 1
                details['higher_lows'] = True
                logger.debug(f"   ✅ Structure bonus: Higher lows confirmed")
        
        else:  # SELL
            # Count consecutive bearish candles
            bearish_count = sum(
                recent.iloc[i]['close'] < recent.iloc[i]['open'] 
                for i in range(len(recent))
            )
            
            # Check for lower highs (downtrend structure)
            highs = recent['high'].values
            lower_highs = all(highs[i] <= highs[i-1] for i in range(1, len(highs)))
            
            if bearish_count >= self.min_consecutive_candles:
                score += 1
                details['consecutive_momentum'] = True
                details['bearish_candles'] = bearish_count
                logger.debug(f"   ✅ Momentum bonus: {bearish_count} bearish candles")
            
            if lower_highs:
                score += 1
                details['lower_highs'] = True
                logger.debug(f"   ✅ Structure bonus: Lower highs confirmed")
        
        return score, details
    
    def _evaluate_buy_signal(self, df_1m: pd.DataFrame, 
                            df_5m: pd.DataFrame) -> Tuple[int, Dict]:
        """Evaluate BUY signal strength"""
        score = 0
        details = {}
        
        latest_1m = df_1m.iloc[-1]
        latest_5m = df_5m.iloc[-1]
        
        # Condition 1: Close > SMA(100)
        if latest_1m['close'] > latest_1m['sma_100']:
            score += 1
            details['close_above_sma'] = True
        
        # Condition 2: EMA(20) > SMA(100)
        if latest_1m['ema_20'] > latest_1m['sma_100']:
            score += 1
            details['ema_above_sma'] = True
        
        # Condition 3: RSI > threshold
        if latest_1m['rsi'] > self.rsi_buy_threshold:
            score += 1
            details['rsi_bullish'] = True
        
        # Condition 4: ADX > threshold (strong trend)
        if latest_1m['adx'] > self.adx_threshold:
            score += 2
            details['strong_trend'] = True
        
        # Condition 5: Last 2 candles bullish
        if len(df_1m) >= 2:
            if is_bullish_candle(df_1m, -1) and is_bullish_candle(df_1m, -2):
                score += 1
                details['consecutive_bullish'] = True
        
        # Condition 6: 5m timeframe confirmation
        if latest_5m['close'] > latest_5m['sma_100']:
            score += 1
            details['5m_confirmation'] = True
        
        details['total_score'] = score
        details['rsi'] = latest_1m['rsi']
        details['adx'] = latest_1m['adx']
        details['atr_1m'] = latest_1m['atr']
        details['atr_5m'] = latest_5m['atr']
        
        return score, details
    
    def _evaluate_sell_signal(self, df_1m: pd.DataFrame, 
                             df_5m: pd.DataFrame) -> Tuple[int, Dict]:
        """Evaluate SELL signal strength"""
        score = 0
        details = {}
        
        latest_1m = df_1m.iloc[-1]
        latest_5m = df_5m.iloc[-1]
        
        # Condition 1: Close < SMA(100)
        if latest_1m['close'] < latest_1m['sma_100']:
            score += 1
            details['close_below_sma'] = True
        
        # Condition 2: EMA(20) < SMA(100)
        if latest_1m['ema_20'] < latest_1m['sma_100']:
            score += 1
            details['ema_below_sma'] = True
        
        # Condition 3: RSI < threshold
        if latest_1m['rsi'] < self.rsi_sell_threshold:
            score += 1
            details['rsi_bearish'] = True
        
        # Condition 4: ADX > threshold (strong trend)
        if latest_1m['adx'] > self.adx_threshold:
            score += 2
            details['strong_trend'] = True
        
        # Condition 5: Last 2 candles bearish
        if len(df_1m) >= 2:
            if is_bearish_candle(df_1m, -1) and is_bearish_candle(df_1m, -2):
                score += 1
                details['consecutive_bearish'] = True
        
        # Condition 6: 5m timeframe confirmation
        if latest_5m['close'] < latest_5m['sma_100']:
            score += 1
            details['5m_confirmation'] = True
        
        details['total_score'] = score
        details['rsi'] = latest_1m['rsi']
        details['adx'] = latest_1m['adx']
        details['atr_1m'] = latest_1m['atr']
        details['atr_5m'] = latest_5m['atr']
        
        return score, details
    
    def _determine_signal(self, buy_score: int, sell_score: int,
                         buy_details: Dict, sell_details: Dict) -> Dict:
        """Determine final trading signal"""
        # Check if either signal meets minimum threshold
        buy_valid = buy_score >= self.minimum_signal_score
        sell_valid = sell_score >= self.minimum_signal_score
        
        if buy_valid and sell_valid:
            # Both signals valid - choose stronger one
            if buy_score > sell_score:
                return self._create_signal('BUY', buy_score, buy_details)
            elif sell_score > buy_score:
                return self._create_signal('SELL', sell_score, sell_details)
            else:
                return self._create_hold_signal("Conflicting signals")
        
        elif buy_valid:
            return self._create_signal('BUY', buy_score, buy_details)
        
        elif sell_valid:
            return self._create_signal('SELL', sell_score, sell_details)
        
        else:
            reason = f"Signals too weak (BUY: {buy_score}, SELL: {sell_score})"
            return self._create_hold_signal(reason)
    
    def _create_signal(self, direction: str, score: int, details: Dict) -> Dict:
        """Create a trading signal dictionary"""
        emoji = get_signal_emoji(direction)
        
        signal = {
            'signal': direction,
            'score': score,
            'details': details,
            'timestamp': pd.Timestamp.now(),
            'can_trade': True
        }
        
        logger.info(f"{emoji} {direction} SIGNAL | Score: {score}/{self.minimum_signal_score+2}")
        logger.info(f"   RSI: {details.get('rsi', 0):.2f} | ADX: {details.get('adx', 0):.2f}")
        
        # Log new confirmations
        if details.get('consecutive_momentum'):
            logger.info(f"   ✅ Momentum confirmed")
        if details.get('higher_lows') or details.get('lower_highs'):
            logger.info(f"   ✅ Structure confirmed")
        
        return signal
    
    def _create_hold_signal(self, reason: str) -> Dict:
        """Create a HOLD signal dictionary"""
        return {
            'signal': 'HOLD',
            'score': 0,
            'details': {'reason': reason},
            'timestamp': pd.Timestamp.now(),
            'can_trade': False
        }