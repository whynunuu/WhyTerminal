# WHY://TERMINAL — Triple Stacked Live Charts, Price Heatmap & Multi-Portal News Wire

Bloomberg/ASCII-style high-density financial trading terminal featuring **Triple Stacked Real-Time Charts** (Gold, Nasdaq, Bitcoin), **Liquidity Price Heatmap**, **Technical Screener**, and **Multi-Portal News Wire**.

Live Web: **https://whynunuu.github.io/WhyTerminal/**  
Security PIN: `202688`

---

## Key Features

### 1. Triple Stacked Live Charts (GC · NQ · BTC)
- **Stacked Architecture (Top to Bottom)**:
  1. **Top**: **GC** (Gold Futures / XAUUSD Spot)
  2. **Middle**: **NQ** (E-Mini Nasdaq 100 Futures / US100)
  3. **Bottom**: **BTC/USD** (Bitcoin / US Dollar)
- **Live Real-Time Market Data**:
  - Direct connection to Binance Public REST API (`/ticker/24hr`, `/klines`, `/depth`) and sub-second WebSocket ticker feed (`wss://stream.binance.com:9443/ws/btcusdt@ticker/paxgusdt@ticker`).
  - Physical Gold spot quotes matching physical London Good Delivery gold.
- **Dual Engine Display**:
  - **Bloomberg ASCII Canvas Mode**: High-density dark retro terminal charts with real OHLCV data, EMA 20/50 ribbons, volume bars, and crosshair tooltips.
  - **TradingView Pro Embed Stream**: 1-click toggle to official institutional CME COMEX/Binance streaming charts with full analysis tools.
- Multi-Timeframe: `1M`, `5M`, `15M`, `1H`, `1D`.

### 2. Price & Liquidity Depth Heatmap
- Replaces legacy numeric tables with a visual **Heatmap Ladder**.
- 18 granular price tiers around current spot price.
- **Visual Heatmap Gradient**:
  - **Asks (Resistance)**: Warm red/orange gradient intensity proportional to sell volume.
  - **Spot Marker**: Glowing active fair value line with real-time price & spread.
  - **Bids (Support)**: Cool green/cyan gradient intensity proportional to buy volume.
- **Order Flow Imbalance Ratio**: Real-time Buy Pressure % vs Sell Pressure % meter.
- **Major Liquidity Wall Detector**: Auto-detects and highlights large liquidity clusters.
- Quick asset switcher: `[GC GOLD]`, `[NQ NASDAQ]`, `[BTC/USD]`.

### 3. Multi-Portal News Wire
- Live curated financial news feed with quick filters for **Bloomberg**, **Reuters**, **CNBC**, **CoinDesk**, **Kontan / IDX**, and **ForexLive**.
- Market sentiment tagging: `[BULLISH ▲]`, `[BEARISH ▼]`, `[NEUTRAL •]`.
- Keyword grep filter and Inspector drawer showing impacted tickers.

### 4. Technical Market Screener
- Auto-scan filters for **RSI Oversold (<35)**, **RSI Overbought (>65)**, **Golden Cross (EMA 20/50)**, and **Volume Surges**.
- 1-Click interactive charting from any screened asset.

### 5. World Sessions & Economic Calendar
- Asian, European, and American session market status with liquidity overlap alerts.
- High-impact macro events calendar (US CPI, FOMC Rate Decision, NFP, BI-Rate).

### 6. Draggable & Resizable Grid Workspace
- 12-column Bloomberg tile workspace with localStorage persistence.
- Audio synthesizer for retro terminal tactile feedback.
- Secure PIN screen (`202688`) with 30-day device remember function.
