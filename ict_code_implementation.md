# ICT Elements: Python Code Implementation and Integration

This document outlines the Python code implementation for key Inner Circle Trader (ICT) concepts, their modular integration into trading strategies, and considerations for incorporating Machine Learning (ML) and robust backtesting.

## 1. Fair Value Gap (FVG)

### Concept
A Fair Value Gap (FVG) represents an inefficiency or imbalance in the market where there is a significant price movement in one direction, leaving a gap between the high of the first candle and the low of the third candle (for a bullish FVG), or vice-versa for a bearish FVG. These gaps are often seen as areas where price is likely to return to for 'mitigation' before continuing its trend.

### Python Implementation (from `smartmoneyconcepts` library)

The `smartmoneyconcepts` library implements FVG detection using `numpy` and `pandas` for efficient array operations. The `fvg` method identifies bullish (1) or bearish (-1) FVGs and their respective `Top`, `Bottom`, and `MitigatedIndex`.

```python
@classmethod
def fvg(cls, ohlc: DataFrame, join_consecutive=False) -> Series:
    fvg = np.where(
        (
            (ohlc["high"].shift(1) < ohlc["low"].shift(-1))
            & (ohlc["close"] > ohlc["open"])
        )
        | (
            (ohlc["low"].shift(1) > ohlc["high"].shift(-1))
            & (ohlc["close"] < ohlc["open"])
        ),
        np.where(ohlc["close"] > ohlc["open"], 1, -1),
        np.nan,
    )

    top = np.where(
        ~np.isnan(fvg),
        np.where(
            ohlc["close"] > ohlc["open"],
            ohlc["low"].shift(-1),
            ohlc["low"].shift(1),
        ),
        np.nan,
    )

    bottom = np.where(
        ~np.isnan(fvg),
        np.where(
            ohlc["close"] > ohlc["open"],
            ohlc["high"].shift(1),
            ohlc["high"].shift(-1),
        ),
        np.nan,
    )

    if join_consecutive:
        for i in range(len(fvg) - 1):
            if fvg[i] == fvg[i + 1]:
                top[i + 1] = max(top[i], top[i + 1])
                bottom[i + 1] = min(bottom[i], bottom[i + 1])
                fvg[i] = top[i] = bottom[i] = np.nan

    mitigated_index = np.zeros(len(ohlc), dtype=np.int32)
    for i in np.where(~np.isnan(fvg))[0]:
        mask = np.zeros(len(ohlc), dtype=np.bool_)
        if fvg[i] == 1:
            mask = ohlc["low"][i + 2 :] <= top[i]
        elif fvg[i] == -1:
            mask = ohlc["high"][i + 2 :] >= bottom[i]
        if np.any(mask):
            j = np.argmax(mask) + i + 2
            mitigated_index[i] = j

    mitigated_index = np.where(np.isnan(fvg), np.nan, mitigated_index)

    return pd.concat(
        [
            pd.Series(fvg, name="FVG"),
            pd.Series(top, name="Top"),
            pd.Series(bottom, name="Bottom"),
            pd.Series(mitigated_index, name="MitigatedIndex"),
        ],
        axis=1,
    )
```

### Explanation

*   **Bullish FVG**: `ohlc["high"].shift(1) < ohlc["low"].shift(-1)` and `ohlc["close"] > ohlc["open"]` (current candle is bullish). The `Top` is the low of the third candle (`ohlc["low"].shift(-1)`) and the `Bottom` is the high of the first candle (`ohlc["high"].shift(1)`).
*   **Bearish FVG**: `ohlc["low"].shift(1) > ohlc["high"].shift(-1)` and `ohlc["close"] < ohlc["open"]` (current candle is bearish). The `Top` is the low of the first candle (`ohlc["low"].shift(1)`) and the `Bottom` is the high of the third candle (`ohlc["high"].shift(-1)`).
*   `join_consecutive`: Merges adjacent FVGs into a single, larger FVG.
*   `MitigatedIndex`: Identifies the first candle that trades into the FVG, indicating its mitigation.

## 2. Market Structure Shift (MSS) / Break of Structure (BOS) / Change of Character (CHoCH)

### Concept
Market Structure Shift (MSS), Break of Structure (BOS), and Change of Character (CHoCH) are crucial for identifying trend reversals and continuations. A BOS indicates a continuation of the current trend, while a CHoCH signals a potential reversal. These are typically identified by price breaking significant swing highs or lows.

### Python Implementation (from `smartmoneyconcepts` library)

The `bos_choch` method relies on previously identified `swing_highs_lows` to determine breaks. It distinguishes between BOS and CHoCH based on whether the break occurs in the direction of the previous trend or against it.

```python
@classmethod
def bos_choch(cls, ohlc: DataFrame, swing_highs_lows: DataFrame, close_break=True) -> Series:
    bos = np.zeros(len(ohlc), dtype=np.int32)
    choch = np.zeros(len(ohlc), dtype=np.int32)
    level = np.zeros(len(ohlc), dtype=np.float64)
    broken_index = np.zeros(len(ohlc), dtype=np.int32)

    for i in range(len(ohlc)):
        if swing_highs_lows["HighLow"][i] == 1:
            # look for a break of structure
            for j in range(i + 1, len(ohlc)):
                if close_break:
                    if ohlc["close"][j] > swing_highs_lows["Level"][i]:
                        bos[j] = 1
                        level[j] = swing_highs_lows["Level"][i]
                        broken_index[j] = i
                        break
                else:
                    if ohlc["high"][j] > swing_highs_lows["Level"][i]:
                        bos[j] = 1
                        level[j] = swing_highs_lows["Level"][i]
                        broken_index[j] = i
                        break

            # look for a change of character
            for j in range(i + 1, len(ohlc)):
                if close_break:
                    if ohlc["close"][j] < swing_highs_lows["Level"][i]:
                        choch[j] = -1
                        level[j] = swing_highs_lows["Level"][i]
                        broken_index[j] = i
                        break
                else:
                    if ohlc["low"][j] < swing_highs_lows["Level"][i]:
                        choch[j] = -1
                        level[j] = swing_highs_lows["Level"][i]
                        broken_index[j] = i
                        break

        elif swing_highs_lows["HighLow"][i] == -1:
            # look for a break of structure
            for j in range(i + 1, len(ohlc)):
                if close_break:
                    if ohlc["close"][j] < swing_highs_lows["Level"][i]:
                        bos[j] = -1
                        level[j] = swing_highs_lows["Level"][i]
                        broken_index[j] = i
                        break
                else:
                    if ohlc["low"][j] < swing_highs_lows["Level"][i]:
                        bos[j] = -1
                        level[j] = swing_highs_lows["Level"][i]
                        broken_index[j] = i
                        break

            # look for a change of character
            for j in range(i + 1, len(ohlc)):
                if close_break:
                    if ohlc["close"][j] > swing_highs_lows["Level"][i]:
                        choch[j] = 1
                        level[j] = swing_highs_lows["Level"][i]
                        broken_index[j] = i
                        break
                else:
                    if ohlc["high"][j] > swing_highs_lows["Level"][i]:
                        choch[j] = 1
                        level[j] = swing_highs_lows["Level"][i]
                        broken_index[j] = i
                        break

    bos = np.where(bos == 0, np.nan, bos)
    choch = np.where(choch == 0, np.nan, choch)
    level = np.where(level == 0, np.nan, level)
    broken_index = np.where(broken_index == 0, np.nan, broken_index)

    return pd.concat(
        [
            pd.Series(bos, name="BOS"),
            pd.Series(choch, name="CHoCH"),
            pd.Series(level, name="Level"),
            pd.Series(broken_index, name="BrokenIndex"),
        ],
        axis=1,
    )
```

### Explanation

*   The function iterates through identified `swing_highs_lows`.
*   For each swing point, it looks for subsequent candles that break above (for bullish BOS/CHoCH) or below (for bearish BOS/CHoCH) that swing point.
*   `close_break`: Determines if the break is confirmed by the closing price or just the high/low.
*   `BOS`: Indicates a continuation of the trend (e.g., price breaks a previous swing high in an uptrend).
*   `CHoCH`: Indicates a potential reversal (e.g., price breaks a previous swing low in an uptrend).

## 3. Order Blocks (OB)

### Concept
Order Blocks are specific candles or groups of candles where large institutional orders were placed, leading to a significant price move. Price often returns to these areas to fill remaining orders before continuing the move. Identifying these zones is key for entry points.

### Python Implementation (from `smartmoneyconcepts` library)

The `ob` method identifies bullish (1) or bearish (-1) order blocks based on `swing_highs_lows` and candle characteristics (open/close relationship). It also calculates `OBVolume` and `Percentage` for strength.

```python
@classmethod
def ob(cls, ohlc: DataFrame, swing_highs_lows: DataFrame, close_mitigation=False) -> Series:
    ob = np.zeros(len(ohlc), dtype=np.int32)
    top = np.zeros(len(ohlc), dtype=np.float64)
    bottom = np.zeros(len(ohlc), dtype=np.float64)
    ob_volume = np.zeros(len(ohlc), dtype=np.float64)
    percentage = np.zeros(len(ohlc), dtype=np.float64)

    for i in range(len(ohlc)):
        if swing_highs_lows["HighLow"][i] == 1:
            # look for a bearish order block
            for j in range(i - 1, 0, -1):
                if ohlc["open"][j] > ohlc["close"][j]:
                    ob[i] = -1
                    top[i] = ohlc["high"][j]
                    bottom[i] = ohlc["low"][j]
                    ob_volume[i] = ohlc["volume"][j] + ohlc["volume"][j - 1] + ohlc["volume"][j - 2]
                    percentage[i] = min(ohlc["volume"][j], ohlc["volume"][j - 1]) / max(ohlc["volume"][j], ohlc["volume"][j - 1])
                    break

        elif swing_highs_lows["HighLow"][i] == -1:
            # look for a bullish order block
            for j in range(i - 1, 0, -1):
                if ohlc["open"][j] < ohlc["close"][j]:
                    ob[i] = 1
                    top[i] = ohlc["high"][j]
                    bottom[i] = ohlc["low"][j]
                    ob_volume[i] = ohlc["volume"][j] + ohlc["volume"][j - 1] + ohlc["volume"][j - 2]
                    percentage[i] = min(ohlc["volume"][j], ohlc["volume"][j - 1]) / max(ohlc["volume"][j], ohlc["volume"][j - 1])
                    break

    # mitigate the order blocks
    for i in np.where(~np.isnan(ob))[0]:
        mask = np.zeros(len(ohlc), dtype=np.bool_)
        if ob[i] == 1:
            if close_mitigation:
                mask = ohlc["close"][i + 1 :] <= top[i]
            else:
                mask = ohlc["low"][i + 1 :] <= top[i]
        elif ob[i] == -1:
            if close_mitigation:
                mask = ohlc["close"][i + 1 :] >= bottom[i]
            else:
                mask = ohlc["high"][i + 1 :] >= bottom[i]
        if np.any(mask):
            ob[i] = top[i] = bottom[i] = ob_volume[i] = percentage[i] = np.nan

    ob = np.where(ob == 0, np.nan, ob)
    top = np.where(top == 0, np.nan, top)
    bottom = np.where(bottom == 0, np.nan, bottom)
    ob_volume = np.where(ob_volume == 0, np.nan, ob_volume)
    percentage = np.where(percentage == 0, np.nan, percentage)

    return pd.concat(
        [
            pd.Series(ob, name="OB"),
            pd.Series(top, name="Top"),
            pd.Series(bottom, name="Bottom"),
            pd.Series(ob_volume, name="OBVolume"),
            pd.Series(percentage, name="Percentage"),
        ],
        axis=1,
    )
```

### Explanation

*   The function looks for specific candles (e.g., a bearish candle before a strong move up for a bullish OB) in relation to `swing_highs_lows`.
*   `close_mitigation`: Determines if the mitigation of the order block is based on the closing price or the high/low.
*   `OBVolume` and `Percentage`: Provide additional context on the strength and validity of the order block.

## 4. Liquidity

### Concept
Liquidity refers to areas in the market where a large number of buy or sell orders are clustered, often around swing highs or lows, or equal highs/lows. These areas act as magnets for price, as institutions often target them to fill their orders. A 
Liquidity sweep occurs when price briefly moves past these levels to trigger stop-losses or fill orders before reversing.

### Python Implementation (from `smartmoneyconcepts` library)

The `liquidity` method identifies areas where multiple swing highs or lows are clustered within a defined `range_percent`. It then checks for `Swept` liquidity, indicating that price has moved past these levels.

```python
@classmethod
def liquidity(cls, ohlc: DataFrame, swing_highs_lows: DataFrame, range_percent=0.01) -> Series:
    liquidity = np.zeros(len(ohlc), dtype=np.int32)
    level = np.zeros(len(ohlc), dtype=np.float64)
    end = np.zeros(len(ohlc), dtype=np.int32)
    swept = np.zeros(len(ohlc), dtype=np.int32)

    for i in range(len(ohlc)):
        if swing_highs_lows["HighLow"][i] == 1:
            # look for multiple highs within a small range of each other
            highs = []
            for j in range(i + 1, len(ohlc)):
                if (ohlc["high"][j] > swing_highs_lows["Level"][i] * (1 - range_percent)) and \
                        (ohlc["high"][j] < swing_highs_lows["Level"][i] * (1 + range_percent)):
                    highs.append(j)
                else:
                    break

            if len(highs) > 1:
                liquidity[i] = 1
                level[i] = swing_highs_lows["Level"][i]
                end[i] = highs[-1]

                # look for a sweep of the liquidity
                for j in range(end[i] + 1, len(ohlc)):
                    if ohlc["high"][j] > level[i]:
                        swept[i] = j
                        break

        elif swing_highs_lows["HighLow"][i] == -1:
            # look for multiple lows within a small range of each other
            lows = []
            for j in range(i + 1, len(ohlc)):
                if (ohlc["low"][j] < swing_highs_lows["Level"][i] * (1 + range_percent)) and \
                        (ohlc["low"][j] > swing_highs_lows["Level"][i] * (1 - range_percent)):
                    lows.append(j)
                else:
                    break

            if len(lows) > 1:
                liquidity[i] = -1
                level[i] = swing_highs_lows["Level"][i]
                end[i] = lows[-1]

                # look for a sweep of the liquidity
                for j in range(end[i] + 1, len(ohlc)):
                    if ohlc["low"][j] < level[i]:
                        swept[i] = j
                        break

    liquidity = np.where(liquidity == 0, np.nan, liquidity)
    level = np.where(level == 0, np.nan, level)
    end = np.where(end == 0, np.nan, end)
    swept = np.where(swept == 0, np.nan, swept)

    return pd.concat(
        [
            pd.Series(liquidity, name="Liquidity"),
            pd.Series(level, name="Level"),
            pd.Series(end, name="End"),
            pd.Series(swept, name="Swept"),
        ],
        axis=1,
    )
```

### Explanation

*   The function identifies clusters of `swing_highs_lows` within a specified `range_percent`.
*   If multiple highs/lows are found, it marks the area as a liquidity zone.
*   It then checks for a `Swept` event, where price moves beyond the identified liquidity level, often indicating a manipulation before a reversal.

## 5. Modular Integration into Strategies

To integrate these ICT elements into a cohesive trading strategy, a modular approach is essential. Each ICT concept can be a separate function or class method that takes OHLCV (Open, High, Low, Close, Volume) data as input and returns the identified patterns or levels. This allows for flexible combination and testing of different ICT confluence factors.

### Example Strategy Structure (Conceptual)

```python
class ICTStrategy:
    def __init__(self, htf_data, ltf_data):
        self.htf_data = htf_data
        self.ltf_data = ltf_data

    def get_htf_bias(self):
        # Apply ICT concepts to HTF data (4H/1H)
        # Example: Detect HTF Market Structure Shift (BOS/CHoCH)
        htf_swings = smc.swing_highs_lows(self.htf_data, swing_length=50) # Adjust swing_length as needed
        htf_bos_choch = smc.bos_choch(self.htf_data, htf_swings)

        # Determine overall bias based on HTF BOS/CHoCH
        # e.g., if latest BOS is bullish, bias is bullish
        # if latest CHoCH is bullish, potential reversal to bullish
        # (Detailed logic to be implemented based on specific ICT rules)
        if htf_bos_choch['BOS'].iloc[-1] == 1: # Example: last BOS is bullish
            return 'bullish'
        elif htf_bos_choch['BOS'].iloc[-1] == -1: # Example: last BOS is bearish
            return 'bearish'
        else:
            return 'neutral'

    def generate_ltf_entry_signals(self, htf_bias):
        # Apply ICT concepts to LTF data (5m/1m) for entry signals
        # Filter signals based on HTF bias

        ltf_swings = smc.swing_highs_lows(self.ltf_data, swing_length=14) # Adjust swing_length
        ltf_fvg = smc.fvg(self.ltf_data)
        ltf_ob = smc.ob(self.ltf_data, ltf_swings)
        ltf_liquidity = smc.liquidity(self.ltf_data, ltf_swings)

        entry_signals = []

        # Example: Bullish entry conditions
        if htf_bias == 'bullish':
            # Look for bullish FVG mitigation in LTF
            # Look for bullish OB mitigation in LTF
            # Look for liquidity sweep followed by CHoCH in LTF
            # (Detailed logic to be implemented)
            pass

        # Example: Bearish entry conditions
        elif htf_bias == 'bearish':
            # Look for bearish FVG mitigation in LTF
            # Look for bearish OB mitigation in LTF
            # Look for liquidity sweep followed by CHoCH in LTF
            # (Detailed logic to be implemented)
            pass

        return entry_signals

    def execute_trade(self, signal):
        # Logic to execute trades via TradeLocker/Binance API
        pass

    def manage_risk(self, trade):
        # Implement prop firm specific risk management (e.g., 2% daily DD)
        pass
```

### Key Integration Principles:

*   **Modularity**: Each ICT concept (FVG, OB, MSS, Liquidity) should be a standalone function or method, making it easy to test and combine.
*   **Multi-Timeframe Confluence**: The strategy should first establish a higher timeframe (HTF) bias (e.g., 4H/1H) using ICT concepts like Market Structure Shift. Lower timeframe (LTF) entry signals (e.g., 5m/1m) are then generated and filtered based on this HTF bias.
*   **Rule-Based Logic**: Translate the visual and discretionary aspects of ICT into explicit, quantifiable rules. For example, an FVG entry might require price to enter a specific percentage of the FVG before a reversal, or an OB entry might require a specific volume profile.

## 6. Integration with Machine Learning (ML) / Artificial Intelligence (AI)

ML/AI can significantly enhance an ICT-based trading engine by addressing the subjective nature of some ICT concepts and improving decision-making.

### a. Market Regime Detection

**Concept**: Markets exhibit different behaviors (e.g., trending, ranging, volatile, calm). A strategy that performs well in a trending market might fail in a ranging market. ML models can classify the current market regime, allowing the trading engine to adapt its strategy or filter signals accordingly.

**Implementation**: This can be achieved using unsupervised learning (e.g., K-Means clustering on volatility, volume, and trend indicators) or supervised learning (training a classifier on labeled market data).

*   **Features**: Volatility (ATR, Standard Deviation), Volume, ADX (Average Directional Index), RSI, MACD, price action patterns.
*   **Models**: K-Means, Hidden Markov Models (HMM), Support Vector Machines (SVM), Random Forests, Neural Networks.

### b. Signal Filtering and Confluence Optimization

**Concept**: Not all ICT setups are equally reliable. ML can learn to identify high-probability setups by analyzing historical data and correlating ICT patterns with subsequent price action.

**Implementation**: Train a classifier to predict the success of an ICT setup (e.g., FVG mitigation leading to a profitable trade).

*   **Features**: Presence/absence of FVG, OB, MSS, Liquidity; size/depth of FVG/OB; volume at OB; HTF bias; proximity to key support/resistance levels; time of day (session).
*   **Models**: Logistic Regression, Random Forests, Gradient Boosting Machines (GBM), Neural Networks.

### c. Pattern Recognition and 
Entry Model Optimization

**Concept**: ML can be used to identify complex price action patterns that are difficult to define with rigid rules, or to optimize entry and exit points within a broader ICT framework.

**Implementation**: Deep learning models, particularly Convolutional Neural Networks (CNNs) for image recognition (treating price charts as images) or Recurrent Neural Networks (RNNs) for sequence analysis, can be trained to recognize specific ICT patterns (e.g., specific FVG mitigation patterns, order block reactions).

*   **Features**: Raw OHLCV data, derived ICT indicators, candlestick patterns.
*   **Models**: CNNs, RNNs (LSTMs, GRUs).

## 7. Backtesting Frameworks

Robust backtesting is crucial for validating ICT strategies and optimizing parameters. Given the multi-timeframe nature of ICT and the need for custom indicator logic, a flexible backtesting framework is required.

### Recommended Frameworks:

1.  **`backtrader`**: A powerful, open-source Python framework for backtesting trading strategies. It supports multi-timeframe analysis, custom indicators, and detailed performance metrics. It's well-suited for implementing rule-based ICT strategies.

    *   **Key Features**: Event-driven architecture, multi-data feed support, extensive indicator library, optimization capabilities, detailed reporting.
    *   **Integration**: ICT indicators (FVG, MSS, OB, Liquidity) can be implemented as custom `backtrader.Indicator` classes, allowing them to be easily integrated into strategies.

2.  **`VectorBT`**: A high-performance Python library for backtesting and research, particularly strong with vectorized operations, making it very fast for large datasets. It's excellent for rapid prototyping and parameter optimization.

    *   **Key Features**: Vectorized backtesting, GPU acceleration, portfolio management, risk analysis, parameter optimization.
    *   **Integration**: ICT indicators can be applied to `pandas` DataFrames, and `VectorBT` can then efficiently backtest strategies based on these indicator outputs.

3.  **Custom Backtesting Engine**: For highly specific or complex ICT strategies, building a custom backtesting engine might be necessary. This offers maximum flexibility but requires more development effort.

    *   **Components**: Data handler (to fetch and manage multi-timeframe data), indicator calculator (to apply ICT logic), strategy executor (to simulate trades), risk manager (to enforce drawdown limits), and performance analyzer.

### Backtesting Considerations for ICT Strategies:

*   **Multi-Timeframe Synchronization**: Ensure that HTF and LTF data are correctly aligned and that indicators from different timeframes are calculated and applied appropriately.
*   **Look-ahead Bias**: Strictly avoid using future data in indicator calculations or decision-making. This is particularly important when dealing with concepts like FVG mitigation or liquidity sweeps, where future price action confirms the pattern.
*   **Slippage and Commissions**: Account for realistic trading costs, especially for high-frequency LTF strategies.
*   **Data Quality**: Use high-quality, tick-level or minute-level data for accurate backtesting, especially for LTF strategies.
*   **Walk-Forward Optimization**: Instead of optimizing parameters on the entire dataset, use walk-forward optimization to simulate real-world trading conditions and assess strategy robustness.
*   **Prop Firm Rules**: Integrate prop firm-specific rules (e.g., daily drawdown limits, maximum drawdown) directly into the backtesting engine to get a realistic assessment of performance under these constraints.

## 8. Code Architecture for Integration

To ensure a clean, modular, and extensible trading engine, the following architecture is recommended:

```
/trading_engine
├── data_manager/
│   ├── __init__.py
│   ├── data_fetcher.py         # Handles data retrieval from Binance/TradeLocker
│   └── data_preprocessor.py    # Handles OHLCV aggregation, resampling, and cleaning
├── indicators/
│   ├── __init__.py
│   ├── ict_indicators.py       # Contains modular FVG, MSS, OB, Liquidity implementations
│   └── ml_indicators.py        # ML models for regime detection, signal filtering
├── strategies/
│   ├── __init__.py
│   ├── base_strategy.py        # Abstract base class for strategies
│   ├── htf_ltf_strategy.py     # Implements multi-timeframe ICT logic
│   └── ml_enhanced_strategy.py # Integrates ML for dynamic decision-making
├── backtesting/
│   ├── __init__.py
│   ├── backtester.py           # Core backtesting logic (e.g., using backtrader/VectorBT)
│   └── performance_analyzer.py # Calculates metrics, generates reports
├── execution/
│   ├── __init__.py
│   ├── tradelocker_api.py      # TradeLocker API client
│   └── binance_api.py          # Binance API client
├── risk_management/
│   ├── __init__.py
│   └── prop_firm_manager.py    # Implements prop firm specific risk rules
├── config/
│   ├── __init__.py
│   └── settings.py             # Configuration for API keys, parameters, etc.
├── main.py                     # Orchestrates the trading engine
└── requirements.txt            # Project dependencies
```

This structure promotes separation of concerns, making it easier to develop, test, and maintain each component independently. The `indicators` module will house the Python implementations of ICT elements, while the `strategies` module will combine these indicators with HTF/LTF logic and ML enhancements. The `backtesting` module will be crucial for iterative development and optimization, and `risk_management` will ensure adherence to prop firm rules.

## References

1.  [Automating Fair Value Gaps (FVG) in Python | by Ziad Francis, PhD](https://medium.com/@ziad.francis/automating-fair-value-gaps-fvg-in-python-0768d3f382e6)
2.  [GitHub - joshyattridge/smart-money-concepts](https://github.com/joshyattridge/smart-money-concepts)
3.  [ICT Market Structure Shift (MSS) — Complete Guide with Examples](https://innercircletrader.net/tutorials/ict-market-structure-shift/)
4.  [Python-Based SMC Automation (Structure + Order Block Logic)](https://www.reddit.com/r/Trading/comments/1qyauat/pythonbased_smc_automation_structure_order_block/)
5.  [backtrader documentation](https://www.backtrader.com/docu/)
6.  [VectorBT documentation](https://vectorbt.dev/docs/))
