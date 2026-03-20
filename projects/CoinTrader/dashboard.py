try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
except ImportError:  # pragma: no cover
    FastAPI = None
    HTMLResponse = None
    JSONResponse = None


def create_dashboard_app(engine):
    if FastAPI is None:
        raise RuntimeError("fastapi is not installed")

    app = FastAPI(title="CoinTrader Dashboard")

    @app.get("/", response_class=HTMLResponse)
    def root():
        return """
            <html>
            <head><title>CoinTrader Dashboard</title></head>
            <body>
              <h1>CoinTrader Dashboard</h1>
              <p><a href='/ui'>Open dashboard UI</a> (recommended)</p>
              <p>Use <a href='/status'>/status</a> for JSON state.</p>
              <p>Use <a href='/signals'>/signals</a> for latest signals.</p>
              <p>Use <a href='/positions'>/positions</a> for current holdings.</p>
              <p>Use <a href='/performance'>/performance</a> for performance metrics.</p>
              <p>Use <a href='/trades'>/trades</a> for recent trade history.</p>
            </body>
            </html>
        """

    @app.get("/status")
    def status():
        return JSONResponse(engine.state)

    @app.get("/signals")
    def signals():
        return JSONResponse({"signals": engine.state.get("last_signals", {})})

    @app.get("/positions")
    def positions():
        return JSONResponse({"positions": engine.state.get("positions", [])})

    @app.get("/alerts")
    def alerts():
        return JSONResponse({"alerts": engine.state.get("alerts", [])})

    @app.get("/performance")
    def performance():
        return JSONResponse({"performance": engine.state.get("performance", {})})

    @app.get("/trades")
    def trades():
        # Get recent trades from trade history csv
        try:
            records = engine.history._load_records()
            return JSONResponse({"trades": records[-50:]})  # Last 50 trades
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=500)

    @app.get("/chart/{symbol}")
    def chart(symbol: str, interval: str = "minute", count: int = 200):
        try:
            ohlcv = engine.upbit.get_ohlcv(symbol, interval=interval, count=count)
            if ohlcv is None:
                return JSONResponse({"error": "no data"}, status_code=404)
            # convert to JSON serializable
            data = []
            for idx, row in ohlcv.iterrows():
                data.append(
                    {
                        "ts": idx.isoformat() if hasattr(idx, "isoformat") else str(idx),
                        "open": float(row.get("open", 0)),
                        "high": float(row.get("high", 0)),
                        "low": float(row.get("low", 0)),
                        "close": float(row.get("close", 0)),
                        "volume": float(row.get("volume", 0)),
                    }
                )
            return JSONResponse({"symbol": symbol, "data": data})
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=500)

    @app.get("/ui", response_class=HTMLResponse)
    def ui():
        symbols = engine.focus if engine.focus else engine.watchlist
        symbols_js = ",".join([f'\"{s}\"' for s in symbols])
        html = """
            <html>
            <head>
              <title>CoinTrader Dashboard</title>
              <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
              <script src="https://cdn.jsdelivr.net/npm/chartjs-adapter-date-fns@3"></script>
            </head>
            <body>
              <h1>CoinTrader Dashboard</h1>
              <label for="symbol">Symbol:</label>
              <select id="symbol"></select>
              <button id="refreshBtn" onclick="refresh()" disabled>Refresh</button>

              <h2>Price Chart</h2>
              <canvas id="chart" width="900" height="400"></canvas>

              <h2>Cumulative P&L Chart</h2>
              <canvas id="pnlChart" width="900" height="250"></canvas>

              <h2>Alerts</h2>
              <pre id="alerts"></pre>

              <h2>Performance</h2>
              <div id="perf">
                <p>Total P&L: <span id="total-pnl">0.00%</span></p>
                <pre id="perf-details"></pre>
              </div>

              <h2>Recent Trades</h2>
              <table id="trades" border="1">
                <thead>
                  <tr>
                    <th>Timestamp</th>
                    <th>Symbol</th>
                    <th>Action</th>
                    <th>Confidence</th>
                    <th>Reason</th>
                    <th>Strategy</th>
                    <th>Regime</th>
                    <th>P&L (%)</th>
                  </tr>
                </thead>
                <tbody></tbody>
              </table>

              <script>
                const symbols = [{symbols_js}];
                const symbolSelect = document.getElementById('symbol');
                symbols.forEach(s => {
                  const opt = document.createElement('option');
                  opt.value = s;
                  opt.text = s;
                  symbolSelect.appendChild(opt);
                });

                let chart;
                let pnlChart;

                function computeSMA(arr, period = 20) {
                  const sma = [];
                  for (let i = 0; i < arr.length; i++) {
                    if (i < period - 1) {
                      sma.push(null);
                      continue;
                    }
                    const slice = arr.slice(i - period + 1, i + 1);
                    const sum = slice.reduce((a, b) => a + b, 0);
                    sma.push(sum / period);
                  }
                  return sma;
                }

                function initCharts() {
                  const ctx = document.getElementById('chart').getContext('2d');
                  chart = new Chart(ctx, {
                    type: 'line',
                    data: {
                      labels: [],
                      datasets: [
                        { label: 'Close Price', data: [], borderColor: 'rgba(54, 162, 235, 1)', backgroundColor: 'rgba(54, 162, 235, 0.1)' },
                        { label: 'SMA (20)', data: [], borderColor: 'rgba(255, 159, 64, 1)', backgroundColor: 'rgba(255, 159, 64, 0.1)' }
                      ]
                    },
                    options: {
                      animation: false,
                      scales: {
                        x: { type: 'time', time: { unit: 'minute', tooltipFormat: 'PPpp' } },
                        y: { beginAtZero: false }
                      },
                      plugins: {
                        legend: { position: 'top' }
                      }
                    }
                  });

                  const pnlCtx = document.getElementById('pnlChart').getContext('2d');
                  pnlChart = new Chart(pnlCtx, {
                    type: 'line',
                    data: {
                      labels: [],
                      datasets: [{ label: 'Cumulative P&L (%)', data: [], borderColor: 'rgba(75, 192, 192, 1)', backgroundColor: 'rgba(75, 192, 192, 0.2)' }]
                    },
                    options: {
                      animation: false,
                      scales: {
                        x: { type: 'time', time: { unit: 'minute', tooltipFormat: 'PPpp' } },
                        y: { beginAtZero: true }
                      }
                    }
                  });
                }

                async function refresh(){
                  if (!chart) {
                    initCharts();                    document.getElementById('refreshBtn').disabled = false;                  }

                  const symbol = symbolSelect.value;
                  const resp = await fetch(`/chart/${symbol}`);
                  const json = await resp.json();
                  if (json.data) {
                    const labels = json.data.map(d => d.ts);
                    const closes = json.data.map(d => d.close);
                    const sma = computeSMA(closes, 20);

                    chart.data.labels = labels;
                    chart.data.datasets[0].data = closes;
                    chart.data.datasets[1].data = sma;
                    chart.update();
                  }

                  const alerts = await fetch('/alerts').then(r=>r.json());
                  document.getElementById('alerts').innerText = JSON.stringify(alerts, null, 2);

                  const perf = await fetch('/performance').then(r=>r.json());
                  document.getElementById('total-pnl').innerText = (perf.performance?.total_pnl || 0).toFixed(2) + '%';
                  document.getElementById('perf-details').innerText = JSON.stringify(perf, null, 2);

                  const tradesResp = await fetch('/trades').then(r=>r.json());
                  const tbody = document.querySelector('#trades tbody');
                  tbody.innerHTML = '';
                  if (tradesResp.trades) {
                    const trades = tradesResp.trades.slice(-50);
                    let cumPnl = 0;
                    const pnlData = [];
                    trades.forEach(t => {
                      const row = tbody.insertRow();
                      row.insertCell().innerText = t.timestamp || '';
                      row.insertCell().innerText = t.symbol || '';
                      const actionCell = row.insertCell();
                      actionCell.innerText = t.action || '';
                      if (t.action?.toLowerCase() === 'buy') {
                        actionCell.style.color = 'green';
                      } else if (t.action?.toLowerCase() === 'sell') {
                        actionCell.style.color = 'red';
                      }
                      row.insertCell().innerText = (t.confidence || 0).toFixed(2);
                      row.insertCell().innerText = t.reason || '';
                      row.insertCell().innerText = t.strategy || '';
                      row.insertCell().innerText = t.regime || '';
                      const pnl = t.pnl ? parseFloat(t.pnl) : 0;
                      const pnlCell = row.insertCell();
                      pnlCell.innerText = pnl ? pnl.toFixed(2) + '%' : '';
                      if (pnl > 0) pnlCell.style.color = 'green';
                      if (pnl < 0) pnlCell.style.color = 'red';

                      if (pnl) {
                        cumPnl += pnl;
                      }
                      pnlData.push({
                        x: t.timestamp,
                        y: cumPnl,
                      });
                    });

                    if (pnlChart) {
                      pnlChart.data.labels = pnlData.map(d=>d.x);
                      pnlChart.data.datasets[0].data = pnlData.map(d=>d.y);
                      pnlChart.update();
                    }
                  }
                }

                refresh();
                setInterval(refresh, 15000);
              </script>
            </body>
            </html>
        """
        return html.replace("{symbols_js}", symbols_js)

    @app.get("/backtest")
    def backtest():
        return JSONResponse({"last_backtest": engine.state.get("last_backtest", {})})

    return app
