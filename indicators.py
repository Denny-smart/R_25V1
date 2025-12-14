"""
Technical Indicators for Deriv R_25 Trading Bot
Implements ATR, RSI, ADX, SMA, EMA, and other indicators
indicators.py
"""

import pandas as pd
import numpy as np
from typing import Tuple

def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """
    Calculate Average True Range (ATR)
    
    Args:
        df: DataFrame with 'high', 'low', 'close' columns
        period: ATR period (default 14)
    
    Returns:
        Series with ATR values
    """
    high = df['high']
    low = df['low']
    close = df['close']
    
    # Calculate True Range
    tr1 = high - low
    tr2 = abs(high - close.shift(1))
    tr3 = abs(low - close.shift(1))
    
    true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    
    # Calculate ATR using EMA
    atr = true_range.ewm(span=period, adjust=False).mean()
    
    return atr

def calculate_rsi(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """
    Calculate Relative Strength Index (RSI)
    
    Args:
        df: DataFrame with 'close' column
        period: RSI period (default 14)
    
    Returns:
        Series with RSI values (0-100)
    """
    close = df['close']
    
    # Calculate price changes
    delta = close.diff()
    
    # Separate gains and losses
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    
    # Calculate average gain and loss
    avg_gain = gain.ewm(span=period, adjust=False).mean()
    avg_loss = loss.ewm(span=period, adjust=False).mean()
    
    # Calculate RS and RSI
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    
    return rsi

def calculate_adx(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """
    Calculate Average Directional Index (ADX)
    
    Args:
        df: DataFrame with 'high', 'low', 'close' columns
        period: ADX period (default 14)
    
    Returns:
        Series with ADX values
    """
    high = df['high']
    low = df['low']
    close = df['close']
    
    # Calculate +DM and -DM
    plus_dm = high.diff()
    minus_dm = -low.diff()
    
    plus_dm[plus_dm < 0] = 0
    minus_dm[minus_dm < 0] = 0
    
    # Calculate True Range
    tr1 = high - low
    tr2 = abs(high - close.shift(1))
    tr3 = abs(low - close.shift(1))
    true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    
    # Smooth the values
    atr = true_range.ewm(span=period, adjust=False).mean()
    plus_di = 100 * (plus_dm.ewm(span=period, adjust=False).mean() / atr)
    minus_di = 100 * (minus_dm.ewm(span=period, adjust=False).mean() / atr)
    
    # Calculate DX and ADX
    dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
    adx = dx.ewm(span=period, adjust=False).mean()
    
    return adx

def calculate_sma(df: pd.DataFrame, period: int = 20) -> pd.Series:
    """
    Calculate Simple Moving Average (SMA)
    
    Args:
        df: DataFrame with 'close' column
        period: SMA period
    
    Returns:
        Series with SMA values
    """
    return df['close'].rolling(window=period).mean()

def calculate_ema(df: pd.DataFrame, period: int = 20) -> pd.Series:
    """
    Calculate Exponential Moving Average (EMA)
    
    Args:
        df: DataFrame with 'close' column
        period: EMA period
    
    Returns:
        Series with EMA values
    """
    return df['close'].ewm(span=period, adjust=False).mean()

def calculate_bollinger_bands(df: pd.DataFrame, period: int = 20, 
                              std_dev: float = 2.0) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """
    Calculate Bollinger Bands
    
    Args:
        df: DataFrame with 'close' column
        period: Period for moving average
        std_dev: Number of standard deviations
    
    Returns:
        Tuple of (upper_band, middle_band, lower_band)
    """
    middle_band = df['close'].rolling(window=period).mean()
    std = df['close'].rolling(window=period).std()
    
    upper_band = middle_band + (std * std_dev)
    lower_band = middle_band - (std * std_dev)
    
    return upper_band, middle_band, lower_band

def calculate_macd(df: pd.DataFrame, fast: int = 12, slow: int = 26, 
                   signal: int = 9) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """
    Calculate MACD (Moving Average Convergence Divergence)
    
    Args:
        df: DataFrame with 'close' column
        fast: Fast EMA period
        slow: Slow EMA period
        signal: Signal line period
    
    Returns:
        Tuple of (macd_line, signal_line, histogram)
    """
    ema_fast = df['close'].ewm(span=fast, adjust=False).mean()
    ema_slow = df['close'].ewm(span=slow, adjust=False).mean()
    
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    
    return macd_line, signal_line, histogram

def is_bullish_candle(df: pd.DataFrame, index: int) -> bool:
    """
    Check if candle at index is bullish
    
    Args:
        df: DataFrame with 'open' and 'close' columns
        index: Index of candle to check
    
    Returns:
        True if bullish, False otherwise
    """
    if index < 0 or index >= len(df):
        return False
    return df.iloc[index]['close'] > df.iloc[index]['open']

def is_bearish_candle(df: pd.DataFrame, index: int) -> bool:
    """
    Check if candle at index is bearish
    
    Args:
        df: DataFrame with 'open' and 'close' columns
        index: Index of candle to check
    
    Returns:
        True if bearish, False otherwise
    """
    if index < 0 or index >= len(df):
        return False
    return df.iloc[index]['close'] < df.iloc[index]['open']

def get_candle_body(df: pd.DataFrame, index: int) -> float:
    """
    Get the body size of a candle
    
    Args:
        df: DataFrame with 'open' and 'close' columns
        index: Index of candle
    
    Returns:
        Absolute body size
    """
    if index < 0 or index >= len(df):
        return 0.0
    return abs(df.iloc[index]['close'] - df.iloc[index]['open'])

def get_candle_range(df: pd.DataFrame, index: int) -> float:
    """
    Get the total range of a candle (high - low)
    
    Args:
        df: DataFrame with 'high' and 'low' columns
        index: Index of candle
    
    Returns:
        Candle range
    """
    if index < 0 or index >= len(df):
        return 0.0
    return df.iloc[index]['high'] - df.iloc[index]['low']

def calculate_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate all technical indicators and add to DataFrame
    
    Args:
        df: DataFrame with OHLC data
    
    Returns:
        DataFrame with all indicators added
    """
    # Create a copy to avoid modifying original
    df = df.copy()
    
    # Calculate indicators
    df['atr'] = calculate_atr(df)
    df['rsi'] = calculate_rsi(df)
    df['adx'] = calculate_adx(df)
    df['sma_100'] = calculate_sma(df, period=100)
    df['ema_20'] = calculate_ema(df, period=20)
    
    # Bollinger Bands
    df['bb_upper'], df['bb_middle'], df['bb_lower'] = calculate_bollinger_bands(df)
    
    # MACD
    df['macd'], df['macd_signal'], df['macd_hist'] = calculate_macd(df)
    
    return df

def get_trend_direction(df: pd.DataFrame) -> str:
    """
    Determine overall trend direction
    
    Args:
        df: DataFrame with indicators
    
    Returns:
        'UP', 'DOWN', or 'SIDEWAYS'
    """
    if len(df) < 100:
        return 'SIDEWAYS'
    
    last_row = df.iloc[-1]
    
    # Check if we have required columns
    if 'close' not in df.columns or 'sma_100' not in df.columns:
        return 'SIDEWAYS'
    
    close = last_row['close']
    sma = last_row['sma_100']
    
    # Strong trend
    if close > sma * 1.002:  # 0.2% above
        return 'UP'
    elif close < sma * 0.998:  # 0.2% below
        return 'DOWN'
    else:
        return 'SIDEWAYS'

# Testing
if __name__ == "__main__":
    # Create sample data
    print("Testing indicators module...")
    
    np.random.seed(42)
    dates = pd.date_range(start='2024-01-01', periods=200, freq='1T')
    
    # Generate sample OHLC data
    close_prices = 100 + np.cumsum(np.random.randn(200) * 0.1)
    data = {
        'timestamp': dates,
        'open': close_prices + np.random.randn(200) * 0.05,
        'high': close_prices + abs(np.random.randn(200) * 0.1),
        'low': close_prices - abs(np.random.randn(200) * 0.1),
        'close': close_prices
    }
    
    df = pd.DataFrame(data)
    
    # Calculate indicators
    print("Calculating ATR...")
    df['atr'] = calculate_atr(df)
    print(f"Latest ATR: {df['atr'].iloc[-1]:.4f}")
    
    print("Calculating RSI...")
    df['rsi'] = calculate_rsi(df)
    print(f"Latest RSI: {df['rsi'].iloc[-1]:.2f}")
    
    print("Calculating ADX...")
    df['adx'] = calculate_adx(df)
    print(f"Latest ADX: {df['adx'].iloc[-1]:.2f}")
    
    print("Calculating SMA...")
    df['sma_100'] = calculate_sma(df, 100)
    print(f"Latest SMA(100): {df['sma_100'].iloc[-1]:.4f}")
    
    print("Calculating EMA...")
    df['ema_20'] = calculate_ema(df, 20)
    print(f"Latest EMA(20): {df['ema_20'].iloc[-1]:.4f}")
    
    # Test candle patterns
    print("\nTesting candle patterns...")
    is_bull = is_bullish_candle(df, -1)
    is_bear = is_bearish_candle(df, -1)
    print(f"Last candle - Bullish: {is_bull}, Bearish: {is_bear}")
    
    # Test trend
    trend = get_trend_direction(df)
    print(f"Current trend: {trend}")
    
    # Calculate all at once
    print("\nCalculating all indicators...")
    df_full = calculate_all_indicators(df)
    print(f"Columns: {list(df_full.columns)}")
    
    print("\n✅ Indicators module test complete!")