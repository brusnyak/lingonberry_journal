# Trading Journal - Implementation Roadmap

## 🎯 Priority 1: cTrader Integration (Highest Impact)

### Why First?
- Eliminates manual data entry errors
- Provides real-time trade monitoring
- Enables automatic trade import
- Foundation for advanced analytics

### Implementation Steps

#### 1. cTrader API Research
- [ ] Review cTrader Open API documentation
- [ ] Test authentication flow (OAuth2)
- [ ] Identify required scopes (read positions, read history)
- [ ] Test rate limits and quotas

#### 2. Create Integration Module
```python
# infra/ctrader_client.py
- authenticate()
- get_positions()
- get_historical_trades()
- get_account_info()
- subscribe_to_position_updates()
```

#### 3. Sync Strategy
- **Initial Sync:** Import last 90 days of trades
- **Incremental Sync:** Poll every 5 minutes for new trades
- **Conflict Resolution:** Use cTrader trade ID as source of truth

#### 4. Data Mapping
```
cTrader Position → Journal Trade
- positionId → external_trade_id
- symbolName → symbol
- tradeSide → direction (BUY=long, SELL=short)
- entryPrice → entry
- stopLoss → sl
- takeProfit → tp
- volume → lot_size
- openTimestamp → ts_open
- closeTimestamp → ts_close
- grossProfit → pnl_usd
```

#### 5. Background Job
- Create `jobs/ctrader_sync.py`
- Run every 5 minutes via APScheduler
- Log sync status to database
- Send Telegram notification on new trades

---

## 🎯 Priority 2: Enhanced Trade Entry

### Current Flow Issues
- Missing critical data points
- No screenshot capture
- No invalidator tracking
- No confluence scoring

### New Trade Entry Flow

#### Telegram Bot Updates
```
/journal
1. Asset type (crypto/forex/stock)
2. Symbol (GBPJPY)
3. Direction (long/short)
4. Entry price
5. Stop loss
6. Take profit
7. Lot size
8. Entry time
9. **NEW: Timeframe (5m/15m/1h/4h/D)**
10. **NEW: Setup type (OB/FVG/BOS/etc.)**
11. **NEW: Confluences (list, e.g., "HTF bullish, daily FVG, NY session")**
12. **NEW: Invalidators (what would make this trade invalid?)**
13. Notes
14. Mood before
15. Market condition
16. **NEW: Screenshot (send image)**
```

#### Database Schema Updates
```sql
ALTER TABLE trades ADD COLUMN confluences_json TEXT;
ALTER TABLE trades ADD COLUMN invalidators_json TEXT;
ALTER TABLE trades ADD COLUMN screenshot_path TEXT;
ALTER TABLE trades ADD COLUMN higher_timeframe_bias TEXT;
ALTER TABLE trades ADD COLUMN key_levels_json TEXT;
```

#### Screenshot Handling
- Store in `data/screenshots/trade_{id}_{timestamp}.png`
- Compress to max 1MB
- Generate thumbnail for list views
- OCR for text extraction (optional)

---

## 🎯 Priority 3: Account Management UI

### New Page: `/accounts`

#### Features
1. **Account List**
   - Card view with key metrics
   - Active account indicator
   - Quick switch button
   - Edit/delete actions

2. **Create Account Form**
   - Prop firm templates (FTMO, MyForexFunds, etc.)
   - Custom rule builder
   - Rule validation
   - Preview before save

3. **Prop Firm Templates**
```python
PROP_FIRM_TEMPLATES = {
    "FTMO": {
        "max_daily_loss_pct": 5.0,
        "max_total_loss_pct": 10.0,
        "profit_target_pct": 10.0,
        "risk_per_trade_pct": 1.0,
        "trailing_drawdown": True,
    },
    "MyForexFunds": {
        "max_daily_loss_pct": 4.0,
        "max_total_loss_pct": 8.0,
        "profit_target_pct": 8.0,
        "risk_per_trade_pct": 1.0,
        "trailing_drawdown": False,
    },
    # ... more templates
}
```

4. **Rule Visualization**
   - Progress bars for daily loss
   - Progress bars for total loss
   - Progress bars for profit target
   - Color-coded risk levels

---

## 🎯 Priority 4: Advanced Analytics

### New Metrics to Calculate

#### 1. Sharpe Ratio
```python
def calculate_sharpe_ratio(trades, risk_free_rate=0.02):
    returns = [t['pnl_pct'] for t in trades]
    avg_return = np.mean(returns)
    std_return = np.std(returns)
    sharpe = (avg_return - risk_free_rate) / std_return
    return sharpe
```

#### 2. Max Drawdown
```python
def calculate_max_drawdown(equity_curve):
    peak = equity_curve[0]
    max_dd = 0
    for balance in equity_curve:
        if balance > peak:
            peak = balance
        dd = (peak - balance) / peak * 100
        if dd > max_dd:
            max_dd = dd
    return max_dd
```

#### 3. Profit Factor
```python
def calculate_profit_factor(trades):
    gross_profit = sum(t['pnl_usd'] for t in trades if t['pnl_usd'] > 0)
    gross_loss = abs(sum(t['pnl_usd'] for t in trades if t['pnl_usd'] < 0))
    return gross_profit / gross_loss if gross_loss > 0 else float('inf')
```

#### 4. Consecutive Wins/Losses
```python
def calculate_streaks(trades):
    current_streak = 0
    max_win_streak = 0
    max_loss_streak = 0
    
    for t in sorted(trades, key=lambda x: x['ts_close']):
        if t['outcome'] == 'TP':
            current_streak = max(0, current_streak) + 1
            max_win_streak = max(max_win_streak, current_streak)
        elif t['outcome'] == 'SL':
            current_streak = min(0, current_streak) - 1
            max_loss_streak = max(max_loss_streak, abs(current_streak))
    
    return max_win_streak, max_loss_streak
```

### New Dashboard Widgets

#### Performance Metrics Panel
```
┌─────────────────────────────────────┐
│ Advanced Metrics                    │
├─────────────────────────────────────┤
│ Sharpe Ratio:        1.45           │
│ Profit Factor:       2.3            │
│ Max Drawdown:        -8.5%          │
│ Avg Trade Duration:  4.2 hours      │
│ Best Streak:         7 wins         │
│ Worst Streak:        3 losses       │
└─────────────────────────────────────┘
```

#### Setup Performance Matrix
```
┌──────────────────────────────────────────────────────┐
│ Setup          Trades  WR%   Avg RR  P&L    Quality  │
├──────────────────────────────────────────────────────┤
│ Order Block    45      68%   1:2.5   +$450  ⭐⭐⭐⭐   │
│ FVG Entry      32      55%   1:1.8   +$120  ⭐⭐⭐     │
│ BOS Retest     28      72%   1:3.1   +$680  ⭐⭐⭐⭐⭐  │
│ Liquidity Grab 15      40%   1:1.2   -$80   ⭐⭐      │
└──────────────────────────────────────────────────────┘
```

#### Calendar Heatmap
```
┌─────────────────────────────────────────────────────┐
│ February 2026                                       │
├─────────────────────────────────────────────────────┤
│ Mon  Tue  Wed  Thu  Fri  Sat  Sun                  │
│ [+2] [+5] [-1] [+3] [+8] [ 0] [ 0]  Week 1: +17    │
│ [+1] [+4] [+2] [-2] [+6] [ 0] [ 0]  Week 2: +11    │
│ [-3] [+2] [+5] [+1] [+4] [ 0] [ 0]  Week 3: +9     │
│ [+6] [+3] [+2] [+7] [+5] [ 0] [ 0]  Week 4: +23    │
└─────────────────────────────────────────────────────┘
Color: Green = profit, Red = loss, intensity = magnitude
```

---

## 🎯 Priority 5: EOD Notification System

### Implementation

#### 1. Scheduler Setup
```python
# bot/journal_daemon.py
from apscheduler.schedulers.background import BackgroundScheduler
from zoneinfo import ZoneInfo

scheduler = BackgroundScheduler()

def send_eod_reminder():
    # Get today's trades
    # Calculate P&L
    # Send summary to Telegram
    pass

scheduler.add_job(
    send_eod_reminder,
    'cron',
    hour=18,
    minute=0,
    timezone=ZoneInfo('Europe/Bratislava')
)
scheduler.start()
```

#### 2. Reminder Content
```
🌙 EOD Reminder - March 1, 2026

📊 Today's Performance:
• Trades: 3 (2W, 1L)
• P&L: +$245 (+2.45%)
• Win Rate: 66.7%

📝 Action Items:
[ ] Review today's trades
[ ] Update trade notes
[ ] Set tomorrow's plan
[ ] Check weekly goals

Tap to open journal 👇
```

#### 3. Customization Options
- Set reminder time per user
- Enable/disable reminders
- Customize reminder content
- Set reminder frequency (daily/weekly)

---

## 🎯 Priority 6: Trade Replay System

### Features

#### 1. Interactive Controls
- Play/Pause button
- Speed control (0.5x, 1x, 2x, 5x)
- Scrubber to jump to specific time
- Entry/Exit markers
- SL/TP lines

#### 2. Drawing Tools
- Trendlines
- Horizontal lines
- Rectangles (zones)
- Fibonacci retracement
- Text annotations
- Save drawings to database

#### 3. Multi-Timeframe View
```
┌─────────────────────────────────────┐
│ 15m Chart                           │
│ [Price action with entry/exit]     │
└─────────────────────────────────────┘
┌─────────────────────────────────────┐
│ 1h Chart (HTF context)              │
│ [Price action with key levels]     │
└─────────────────────────────────────┘
```

#### 4. Indicator Overlays
- Moving averages
- RSI
- MACD
- Volume
- Custom indicators

---

## 🎯 Priority 7: Weekly Goal Tracking

### Goal Types

#### 1. Stick to Plan
```
Goal: Follow trading plan
Plan: 
- Max 2 trades per day
- Only trade London/NY sessions
- Min 1:2 RR
- Wait for confirmation

Progress: 4/5 days followed ✅
```

#### 2. Win Count Target
```
Goal: 10 winning trades this week
Progress: 7/10 (70%) 🟡
Remaining: 3 trades
Days left: 2
```

#### 3. Daily % Target
```
Goal: Make 1% per day
Progress:
Mon: +1.2% ✅
Tue: +0.8% 🟡
Wed: +1.5% ✅
Thu: -0.5% ❌
Fri: +2.1% ✅

Average: +1.02% ✅
```

#### 4. Max Trades Per Day
```
Goal: Max 3 trades per day
Progress:
Mon: 2/3 ✅
Tue: 3/3 ✅
Wed: 4/3 ❌ (violated)
Thu: 1/3 ✅
Fri: 2/3 ✅
```

### Goal Dashboard Widget
```
┌─────────────────────────────────────┐
│ Weekly Goals (Week of Feb 24)      │
├─────────────────────────────────────┤
│ ✅ Stick to plan: 4/5 days          │
│ 🟡 Win target: 7/10 trades          │
│ ✅ Daily %: +1.02% avg              │
│ ❌ Max trades: 1 violation          │
└─────────────────────────────────────┘
```

---

## 🎯 Priority 8: Telegram Mini App

### Implementation Steps

#### 1. Telegram WebApp API Integration
```javascript
// webapp/static/js/telegram-webapp.js
const tg = window.Telegram.WebApp;

// Initialize
tg.ready();
tg.expand();

// Theme
const theme = tg.colorScheme; // 'light' or 'dark'
document.documentElement.setAttribute('data-theme', theme);

// User info
const user = tg.initDataUnsafe.user;
console.log(user.id, user.first_name);

// Haptic feedback
tg.HapticFeedback.impactOccurred('medium');

// Main button
tg.MainButton.setText('Save Trade');
tg.MainButton.onClick(() => {
    // Save logic
});
tg.MainButton.show();
```

#### 2. Mobile-Optimized UI
- Touch-friendly buttons (min 44x44px)
- Swipe gestures for navigation
- Bottom sheet modals
- Pull-to-refresh
- Infinite scroll for trade list

#### 3. Telegram-Specific Features
- Share trade to chat
- Forward trade report
- Inline query for quick stats
- Bot commands in chat
- Notification badges

---

## 📅 Implementation Timeline

### Week 1-2: Foundation
- [ ] cTrader API integration
- [ ] Enhanced trade entry flow
- [ ] Screenshot handling
- [ ] Database schema updates

### Week 3-4: Analytics
- [ ] Advanced metrics calculation
- [ ] Setup performance tracking
- [ ] Calendar heatmap
- [ ] New dashboard widgets

### Week 5-6: Management
- [ ] Account management UI
- [ ] Prop firm templates
- [ ] Weekly goal tracking
- [ ] Goal progress indicators

### Week 7-8: Review & Replay
- [ ] Interactive trade replay
- [ ] Drawing tools
- [ ] Multi-timeframe view
- [ ] Structured review system

### Week 9-10: Telegram Mini App
- [ ] WebApp API integration
- [ ] Mobile UI optimization
- [ ] Telegram-specific features
- [ ] Testing & polish

### Week 11-12: Polish & Deploy
- [ ] Bug fixes
- [ ] Performance optimization
- [ ] Documentation
- [ ] Production deployment

---

## 🔧 Technical Requirements

### Dependencies to Add
```
# requirements.txt additions
requests-oauthlib==1.3.1  # cTrader OAuth
Pillow==10.2.0            # Screenshot processing
numpy==1.26.4             # Advanced calculations
scipy==1.12.0             # Statistical analysis
plotly==5.18.0            # Interactive charts
```

### Environment Variables
```
# .env additions
CTRADER_API_URL=https://api.ctrader.com
CTRADER_SYNC_INTERVAL=300  # seconds
SCREENSHOT_MAX_SIZE=1048576  # 1MB
TELEGRAM_WEBAPP_URL=https://your-domain.com
```

---

**End of Roadmap**
