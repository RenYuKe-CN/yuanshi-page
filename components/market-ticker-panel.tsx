"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { Activity, BarChart3, BrainCircuit, Radio, RefreshCw, ShieldAlert, TrendingDown, TrendingUp, Zap } from "lucide-react";
import { api } from "@/components/api";

type SymbolName = "BTC-USDT" | "ETH-USDT" | "SOL-USDT" | "BNB-USDT" | "OKB-USDT";

type Ticker = {
  symbol: SymbolName;
  base: "BTC" | "ETH" | "SOL" | "BNB" | "OKB";
  venue: "OKX" | "Binance" | "CMC";
  marketType: "SWAP" | "SPOT" | "QUOTE";
  price: number;
  indexPrice: number | null;
  change24h: number | null;
  high24h: number | null;
  low24h: number | null;
  volume24h: number | null;
  updatedAt: string;
};

type Payload = {
  source: string;
  items: Ticker[];
  generatedAt: string;
};

type ChartPoint = {
  time: string;
  price: number;
  volume: number;
};

type EChartsInstance = {
  setOption(option: unknown): void;
  resize(): void;
  dispose(): void;
};

type EChartsGlobal = {
  init(element: HTMLDivElement): EChartsInstance;
};

declare global {
  interface Window {
    echarts?: EChartsGlobal;
  }
}

const DEFAULT_SYMBOLS: SymbolName[] = ["BTC-USDT", "ETH-USDT", "SOL-USDT", "BNB-USDT", "OKB-USDT"];

function money(value: number | null) {
  if (value === null) return "-";
  return value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function compact(value: number | null) {
  if (value === null) return "-";
  return Intl.NumberFormat(undefined, { notation: "compact", maximumFractionDigits: 2 }).format(value);
}

function pct(value: number | null) {
  if (value === null) return "实时";
  return `${value >= 0 ? "+" : ""}${value.toFixed(2)}%`;
}

function scoreFrom(items: Ticker[]) {
  if (!items.length) return 0;
  const avg = items.reduce((sum, item) => sum + (item.change24h || 0), 0) / items.length;
  return Math.max(0, Math.min(100, Math.round(50 + avg * 7)));
}

function metricBars(items: Ticker[]) {
  const score = scoreFrom(items);
  const vol = Math.min(100, Math.round(Math.log10(Math.max(10, items.reduce((sum, item) => sum + (item.volume24h || 0), 0))) * 10));
  const wins = Math.round((items.filter((item) => (item.change24h || 0) >= 0).length / Math.max(1, items.length)) * 100);
  const risk = Math.max(8, Math.min(92, Math.round(100 - score + vol * 0.18)));
  const odds = Math.max(35, Math.min(95, Math.round((score + wins) / 2)));
  const position = Math.max(10, Math.min(90, Math.round(score * 0.72)));
  const ev = Math.max(0, Math.min(100, Math.round(score * 0.65 + wins * 0.2 - risk * 0.12)));
  return [
    ["VOL", vol, "成交热度"],
    ["SCORE", score, "综合评分"],
    ["胜率", wins, "方向一致"],
    ["赔率", odds, "机会质量"],
    ["风险", risk, "波动风险"],
    ["仓位", position, "建议暴露"],
    ["EV", ev, "期望值"]
  ] as const;
}

function loadECharts() {
  if (window.echarts) return Promise.resolve(window.echarts);
  return new Promise<EChartsGlobal>((resolve, reject) => {
    const script = document.createElement("script");
    script.src = "https://cdn.jsdelivr.net/npm/echarts@5.6.0/dist/echarts.min.js";
    script.async = true;
    script.onload = () => window.echarts ? resolve(window.echarts) : reject(new Error("ECharts 加载失败"));
    script.onerror = () => reject(new Error("ECharts 加载失败"));
    document.head.appendChild(script);
  });
}

export function MarketTickerPanel() {
  const [data, setData] = useState<Payload | null>(null);
  const [active, setActive] = useState<SymbolName>("BTC-USDT");
  const [history, setHistory] = useState<Record<SymbolName, ChartPoint[]>>({
    "BTC-USDT": [],
    "ETH-USDT": [],
    "SOL-USDT": [],
    "BNB-USDT": [],
    "OKB-USDT": []
  });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const chartRef = useRef<HTMLDivElement | null>(null);
  const chartInstance = useRef<EChartsInstance | null>(null);

  const items = data?.items.length ? data.items : DEFAULT_SYMBOLS.map((symbol) => ({
    symbol,
    base: symbol.split("-")[0] as Ticker["base"],
    venue: "OKX",
    marketType: "SPOT",
    price: 0,
    indexPrice: null,
    change24h: null,
    high24h: null,
    low24h: null,
    volume24h: null,
    updatedAt: new Date().toISOString()
  } satisfies Ticker));
  const activeTicker = items.find((item) => item.symbol === active) || items[0];
  const metrics = useMemo(() => metricBars(activeTicker && activeTicker.price > 0 ? [activeTicker] : items.filter((item) => item.price > 0)), [activeTicker, items]);
  const chartPoints = useMemo(() => history[active] || [], [history, active]);

  async function load() {
    setLoading(true);
    try {
      const payload = await api<Payload>("/api/market/tickers");
      setData(payload);
      setHistory((current) => {
        const next = { ...current };
        for (const item of payload.items) {
          next[item.symbol] = [
            ...(next[item.symbol] || []),
            {
              time: new Date(item.updatedAt).toLocaleTimeString(),
              price: item.price,
              volume: item.volume24h || 0
            }
          ].slice(-48);
        }
        return next;
      });
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "行情读取失败");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    const timer = window.setInterval(load, 10_000);
    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    if (!chartRef.current) return;
    let cancelled = false;
    loadECharts().then((echarts) => {
      if (cancelled || !chartRef.current) return;
      chartInstance.current ||= echarts.init(chartRef.current);
      chartInstance.current.setOption({
        backgroundColor: "transparent",
        grid: { left: 44, right: 18, top: 30, bottom: 34 },
        tooltip: { trigger: "axis", backgroundColor: "rgba(3,8,16,.94)", borderColor: "rgba(245,196,81,.35)", textStyle: { color: "#e5eefc" } },
        xAxis: { type: "category", data: chartPoints.map((point) => point.time), axisLine: { lineStyle: { color: "rgba(255,255,255,.16)" } }, axisLabel: { color: "#64748b", fontSize: 10 } },
        yAxis: [
          { type: "value", scale: true, axisLabel: { color: "#64748b", fontSize: 10 }, splitLine: { lineStyle: { color: "rgba(255,255,255,.06)" } } },
          { type: "value", show: false }
        ],
        series: [
          {
            name: "价格",
            type: "line",
            smooth: true,
            showSymbol: false,
            data: chartPoints.map((point) => point.price),
            lineStyle: { width: 3, color: "#f5c451", shadowColor: "rgba(245,196,81,.45)", shadowBlur: 12 },
            areaStyle: { color: { type: "linear", x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: "rgba(245,196,81,.28)" }, { offset: 1, color: "rgba(245,196,81,0)" }] } }
          },
          {
            name: "量能",
            type: "bar",
            yAxisIndex: 1,
            data: chartPoints.map((point) => point.volume),
            itemStyle: { color: "rgba(34,211,238,.28)", borderRadius: [3, 3, 0, 0] }
          }
        ]
      });
    }).catch(() => undefined);
    const onResize = () => chartInstance.current?.resize();
    window.addEventListener("resize", onResize);
    return () => {
      cancelled = true;
      window.removeEventListener("resize", onResize);
    };
  }, [active, chartPoints]);

  return (
    <section className="cyber-dashboard rounded-[2rem] p-5 md:p-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs font-black tracking-[.28em] text-cyan-300">REALTIME MARKET MATRIX</p>
          <h2 className="cyber-title mt-2 text-2xl font-black tracking-[-.06em] md:text-3xl">USDT 实时行情四象限</h2>
          <p className="mt-1 text-xs text-slate-500">BTC / ETH / SOL / BNB / OKB，参考 Binance、OKX 与 CMC 公开行情。每 10 秒刷新。</p>
        </div>
        <button onClick={load} className="inline-flex items-center gap-2 rounded-xl border border-cyan-300/20 bg-cyan-300/5 px-3 py-2 text-xs font-bold text-cyan-100 hover:border-amber-400/40 hover:text-amber-200">
          <RefreshCw size={14} className={loading ? "animate-spin text-amber-300" : "text-amber-300"} />
          SYNC
        </button>
      </div>

      <div className="mt-5 grid gap-4 xl:grid-cols-2">
        <article className="cyber-panel min-h-[330px] rounded-3xl p-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="text-[10px] font-black tracking-[.22em] text-slate-500">HIGH FREQUENCY TICK</p>
              <h3 className="mt-1 font-['Orbitron'] text-lg font-black text-white">{active} 分时图</h3>
            </div>
            <div className="text-right">
              <div className="font-['JetBrains_Mono'] text-2xl font-black text-white">${money(activeTicker?.price || null)}</div>
              <div className={`text-xs font-black ${(activeTicker?.change24h || 0) >= 0 ? "text-emerald-300" : "text-red-300"}`}>{pct(activeTicker?.change24h ?? null)}</div>
            </div>
          </div>
          <div ref={chartRef} className="mt-3 h-56 w-full" />
          <div className="flex flex-wrap gap-2">
            {items.map((item) => (
              <button key={item.symbol} onClick={() => setActive(item.symbol)} className={`rounded-full border px-3 py-1.5 text-[11px] font-black transition ${active === item.symbol ? "border-amber-400/60 bg-amber-400/15 text-amber-200" : "border-white/10 bg-white/[.03] text-slate-400 hover:border-cyan-300/30 hover:text-white"}`}>{item.base}</button>
            ))}
          </div>
        </article>

        <article className="cyber-panel rounded-3xl p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-[10px] font-black tracking-[.22em] text-slate-500">SIGNAL ENGINE</p>
              <h3 className="mt-1 font-['Orbitron'] text-lg font-black text-white">信号引擎</h3>
            </div>
            <BrainCircuit className="text-amber-300" size={24} />
          </div>
          <div className="mt-5 space-y-3">
            {metrics.map(([label, value, note]) => (
              <div key={label} className="grid grid-cols-[72px_1fr_46px] items-center gap-3">
                <div>
                  <p className="font-['JetBrains_Mono'] text-xs font-black text-white">{label}</p>
                  <p className="text-[10px] text-slate-600">{note}</p>
                </div>
                <div className="h-3 overflow-hidden rounded-full border border-white/10 bg-black/30">
                  <div className={`h-full rounded-full ${label === "风险" ? "bg-gradient-to-r from-amber-500 to-red-400" : "bg-gradient-to-r from-cyan-400 to-emerald-300"}`} style={{ width: `${value}%` }} />
                </div>
                <div className="font-['JetBrains_Mono'] text-right text-sm font-black text-amber-200">{value}</div>
              </div>
            ))}
          </div>
        </article>

        <article className="cyber-panel rounded-3xl p-4">
          <div className="flex items-center gap-2"><BarChart3 size={18} className="text-cyan-300" /><h3 className="font-['Orbitron'] font-black text-white">USDT 对矩阵</h3></div>
          <div className="mt-4 grid gap-2 sm:grid-cols-2">
            {items.map((item) => {
              const up = (item.change24h || 0) >= 0;
              const Trend = up ? TrendingUp : TrendingDown;
              return (
                <button key={item.symbol} onClick={() => setActive(item.symbol)} className={`group rounded-2xl border p-3 text-left transition hover:shadow-[0_0_28px_rgba(34,211,238,.12)] ${active === item.symbol ? "border-amber-400/50 bg-amber-400/10" : "border-white/10 bg-white/[.025] hover:border-cyan-300/30"}`}>
                  <div className="flex items-center justify-between gap-3">
                    <div><p className="font-['Orbitron'] text-sm font-black text-white">{item.symbol}</p><p className="text-[10px] font-bold text-slate-600">{item.venue} · {item.marketType}</p></div>
                    <Trend size={16} className={up ? "text-emerald-300" : "text-red-300"} />
                  </div>
                  <div className="mt-3 font-['JetBrains_Mono'] text-xl font-black text-white">${money(item.price || null)}</div>
                  <div className={`mt-1 text-xs font-black ${up ? "text-emerald-300" : "text-red-300"}`}>{pct(item.change24h)}</div>
                </button>
              );
            })}
          </div>
        </article>

        <article className="cyber-panel rounded-3xl p-4">
          <div className="flex items-center gap-2"><ShieldAlert size={18} className="text-amber-300" /><h3 className="font-['Orbitron'] font-black text-white">市场状态</h3></div>
          <div className="mt-4 grid gap-3">
            <InfoRow label="数据源" value={data?.source || "OKX / Binance / CMC"} icon={<Radio size={15} />} />
            <InfoRow label="刷新频率" value="10 秒" icon={<Zap size={15} />} />
            <InfoRow label="跟踪资产" value="BTC ETH SOL BNB OKB" icon={<Activity size={15} />} />
          </div>
          <div className="mt-5 rounded-2xl border border-amber-400/15 bg-amber-400/5 p-4 text-xs leading-6 text-slate-400">
            {error || "价格来自公开行情接口，仅作为业务看板参考；实际交易请以交易所成交页为准。"}
          </div>
          <p className="mt-3 text-[11px] text-slate-600">{data?.generatedAt ? `最后更新：${new Date(data.generatedAt).toLocaleString()}` : "等待行情更新"}</p>
        </article>
      </div>
    </section>
  );
}

function InfoRow({ label, value, icon }: { label: string; value: string; icon: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between rounded-2xl border border-white/10 bg-white/[.025] px-4 py-3">
      <div className="flex items-center gap-2 text-slate-500">{icon}<span className="text-xs font-bold">{label}</span></div>
      <span className="font-['JetBrains_Mono'] text-xs font-black text-white">{value}</span>
    </div>
  );
}
