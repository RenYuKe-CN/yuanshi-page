"use client";

import { useEffect, useState } from "react";
import { Activity, BadgeDollarSign, Crown, Database, Radio, ReceiptText, Rocket, UserPlus } from "lucide-react";
import { api } from "@/components/api";

type Point = { date: string; value: number };
type Analytics = {
  metrics: {
    totalRevenue: number;
    paymentCount: number;
    starshipMembers: number;
    proMembers: number;
    todayQueries: number;
    totalQueries: number;
    active24h: number;
    registrations: number;
  };
  series: {
    registrations: Point[];
    active: Point[];
    queries: Point[];
    revenue: Point[];
  };
  generatedAt: string;
};

export function AnalyticsPanel() {
  const [data, setData] = useState<Analytics | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    api<Analytics>("/api/admin/analytics").then(setData).catch((err) => setError(err instanceof Error ? err.message : "读取失败"));
  }, []);

  if (error) return <div className="rounded-2xl border border-red-400/20 bg-red-400/5 p-4 text-sm text-red-300">{error}</div>;
  if (!data) return <div className="glass-card rounded-2xl p-10 text-center text-sm text-slate-600">经营数据加载中...</div>;

  const metrics = [
    ["累计收款", `$${data.metrics.totalRevenue.toLocaleString(undefined, { minimumFractionDigits: 2 })}`, BadgeDollarSign, true],
    ["收款笔数", data.metrics.paymentCount.toLocaleString(), ReceiptText, false],
    ["星舰会员", data.metrics.starshipMembers.toLocaleString(), Rocket, false],
    ["旗舰 PRO", data.metrics.proMembers.toLocaleString(), Crown, true],
    ["今日 IP 调用", data.metrics.todayQueries.toLocaleString(), Activity, false],
    ["累计 IP 调用", data.metrics.totalQueries.toLocaleString(), Database, false],
    ["24H 在线活跃", data.metrics.active24h.toLocaleString(), Radio, true],
    ["总注册人数", data.metrics.registrations.toLocaleString(), UserPlus, false]
  ] as const;

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-xs font-semibold tracking-[.24em] text-emerald-400">BUSINESS INTELLIGENCE</p>
          <h2 className="mt-2 text-xl font-bold text-white">会员经营数据</h2>
          <p className="mt-1 text-xs text-slate-600">仅统计普通注册用户；收款只计入链上验证成功的 PAID 订单。</p>
        </div>
        <span className="text-[11px] text-slate-600">更新于 {new Date(data.generatedAt).toLocaleString()}</span>
      </div>
      <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {metrics.map(([label, value, Icon, green]) => (
          <div key={label} className="rounded-2xl border border-white/10 bg-[#11161d] p-5 shadow-[inset_0_1px_rgba(255,255,255,.03)]">
            <div className="flex items-center justify-between text-xs font-semibold text-slate-500"><span>{label}</span><Icon size={16} className={green ? "text-emerald-400" : "text-amber-400"} /></div>
            <div className={`mt-4 text-2xl font-bold tracking-tight ${green ? "text-emerald-400" : "text-white"}`}>{value}</div>
          </div>
        ))}
      </section>
      <section className="grid gap-4 lg:grid-cols-2">
        <TrendCard title="用户增长 · 近 30 天" points={data.series.registrations} type="line" />
        <TrendCard title="24 小时活跃 · 近 30 天" points={data.series.active} type="line" />
        <TrendCard title="每日 IP 调用 · 近 30 天" points={data.series.queries} type="bars" />
        <TrendCard title="每日收款 · 近 30 天" points={data.series.revenue} type="bars" money />
      </section>
    </div>
  );
}

function TrendCard({ title, points, type, money = false }: { title: string; points: Point[]; type: "line" | "bars"; money?: boolean }) {
  const width = 640;
  const height = 210;
  const max = Math.max(1, ...points.map((point) => point.value));
  const coords = points.map((point, index) => ({
    x: (index / Math.max(1, points.length - 1)) * width,
    y: height - (point.value / max) * (height - 30)
  }));
  const line = coords.map((point) => `${point.x},${point.y}`).join(" ");
  const total = points.reduce((sum, point) => sum + point.value, 0);
  const gradientId = `trend-${Array.from(title).reduce((sum, char) => sum + char.charCodeAt(0), 0)}`;
  return (
    <article className="rounded-2xl border border-white/10 bg-[#11161d] p-5">
      <div className="flex items-center justify-between"><h3 className="text-sm font-semibold text-slate-400">{title}</h3><span className="font-mono text-sm font-bold text-emerald-400">{money ? "$" : ""}{total.toLocaleString()}</span></div>
      <div className="mt-5 h-52 overflow-hidden">
        <svg viewBox={`0 0 ${width} ${height}`} className="h-full w-full" preserveAspectRatio="none" aria-label={title}>
          <defs><linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#4ade80" stopOpacity=".28" /><stop offset="100%" stopColor="#4ade80" stopOpacity="0" /></linearGradient></defs>
          {type === "line" ? <>
            <polygon points={`0,${height} ${line} ${width},${height}`} fill={`url(#${gradientId})`} />
            <polyline points={line} fill="none" stroke="#4ade80" strokeWidth="3" vectorEffect="non-scaling-stroke" />
          </> : points.map((point, index) => {
            const barWidth = width / points.length - 5;
            const barHeight = (point.value / max) * (height - 20);
            return <rect key={point.date} x={index * (width / points.length) + 2} y={height - barHeight} width={Math.max(2, barWidth)} height={barHeight} rx="3" fill="#4ade80" opacity={point.value ? .9 : .15} />;
          })}
        </svg>
      </div>
      <div className="flex justify-between text-[10px] text-slate-700"><span>{points[0]?.date.slice(5)}</span><span>{points.at(-1)?.date.slice(5)}</span></div>
    </article>
  );
}
