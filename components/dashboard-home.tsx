"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Activity, ArrowRight, BadgeCheck, Database, Gauge, Megaphone, Search, Zap } from "lucide-react";
import { api } from "@/components/api";
import { ExchangeName } from "@/components/exchange-picker";
import { MarketTickerPanel } from "@/components/market-ticker-panel";

type DashboardData = {
  stats: {
    member: {
      planName: string;
      status: string;
      remaining: number | null;
      unlimited: boolean;
      expiresAt: string | null;
    };
    today: number;
    month: number;
    total: number;
  };
  recent: Array<{
    id: string;
    fullIp: string;
    exchange: string;
    lastSimilarity: number;
    lastSeenAt: string;
  }>;
};

type Announcement = {
  id: string;
  title: string;
  content: string;
  type: string;
  popup: boolean;
  publishedAt: string;
};

export function DashboardHome() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [announcements, setAnnouncements] = useState<Announcement[]>([]);
  const [popup, setPopup] = useState<Announcement | null>(null);

  useEffect(() => {
    Promise.all([
      api<DashboardData>("/api/dashboard"),
      api<{ announcements: Announcement[] }>("/api/announcements")
    ]).then(([dashboard, notice]) => {
      setData(dashboard);
      setAnnouncements(notice.announcements);
      const next = notice.announcements.find((item) => item.popup && localStorage.getItem(`notice:${item.id}`) !== "dismissed");
      setPopup(next || null);
    });
  }, []);

  function dismissPopup() {
    if (popup) localStorage.setItem(`notice:${popup.id}`, "dismissed");
    setPopup(null);
  }

  const stats = [
    { label: "当前会员", value: data?.stats.member.planName || "加载中", icon: BadgeCheck, note: data?.stats.member.status || "-" },
    { label: "本月剩余次数", value: data?.stats.member.unlimited ? "无限" : String(data?.stats.member.remaining ?? 0), icon: Gauge, note: data?.stats.member.expiresAt ? `${new Date(data.stats.member.expiresAt).toLocaleDateString()} 到期` : "暂无到期日" },
    { label: "今日查询", value: String(data?.stats.today ?? 0), icon: Zap, note: `本月 ${data?.stats.month ?? 0} 次` },
    { label: "总查询", value: String(data?.stats.total ?? 0), icon: Database, note: "累计业务查询" }
  ];

  return (
    <div className="space-y-6">
      <section className="premium-hero rounded-[2rem] px-6 py-9 md:px-9">
        <div className="relative max-w-2xl">
          <p className="inline-flex rounded-full border border-amber-400/20 bg-amber-400/10 px-3 py-1.5 text-[11px] font-black tracking-[.22em] text-amber-300">DIGITAL ASSET OPERATIONS</p>
          <h1 className="mt-4 text-4xl font-black tracking-[-.06em] text-white md:text-5xl">原石金手指</h1>
          <p className="mt-3 text-sm leading-7 text-slate-400">统一管理交易所网络环境，快速检测 IP 重复率，用清晰可靠的数据降低环境冲突风险。</p>
          <div className="mt-6 flex flex-wrap gap-3">
            <Link href="/ip-query" className="gold-button inline-flex items-center gap-2 rounded-xl px-5 py-3 text-sm font-bold"><Search size={17} />快捷查询</Link>
            <Link href="/membership" className="inline-flex items-center gap-2 rounded-xl border border-white/10 bg-white/5 px-5 py-3 text-sm font-bold text-slate-300 transition hover:border-amber-400/25 hover:bg-amber-400/5 hover:text-white">会员中心<ArrowRight size={16} /></Link>
          </div>
        </div>
      </section>

      <MarketTickerPanel />

      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {stats.map(({ label, value, icon: Icon, note }, index) => (
          <div key={label} className="glass-card rise-in rounded-3xl p-5" style={{ animationDelay: `${index * 50}ms` }}>
            <div className="flex items-center justify-between">
              <span className="text-xs font-black uppercase tracking-[.16em] text-slate-500">{label}</span>
              <span className="grid h-10 w-10 place-items-center rounded-2xl border border-amber-400/20 bg-amber-400/10 text-amber-300"><Icon size={18} /></span>
            </div>
            <div className="mt-4 text-3xl font-black tracking-[-.05em] text-white">{value}</div>
            <div className="mt-1 text-xs text-slate-600">{note}</div>
          </div>
        ))}
      </section>

      <section className="grid gap-5 xl:grid-cols-[1.4fr_.8fr]">
        <div className="glass-card rounded-3xl">
          <div className="flex items-center justify-between border-b border-white/5 px-5 py-4">
            <div><h2 className="font-semibold text-white">最近查询</h2><p className="mt-1 text-xs text-slate-600">最新网络环境记录</p></div>
            <Link href="/history" className="text-xs font-semibold text-amber-400">查看全部</Link>
          </div>
          <div className="divide-y divide-white/5">
            {data?.recent.length ? data.recent.map((item) => (
              <div key={item.id} className="grid grid-cols-[1fr_auto] gap-3 px-5 py-4 text-sm md:grid-cols-[1fr_1fr_auto_auto]">
                <span className="font-mono text-slate-200">{item.fullIp}</span>
                <ExchangeName name={item.exchange} />
                <span className={`status-${item.lastSimilarity} rounded-lg border px-2 py-1 text-xs`}>{item.lastSimilarity}%</span>
                <span className="hidden text-xs text-slate-600 md:block">{new Date(item.lastSeenAt).toLocaleString()}</span>
              </div>
            )) : <div className="px-5 py-10 text-center text-sm text-slate-600">暂无查询记录</div>}
          </div>
        </div>

        <div className="glass-card rounded-3xl p-5">
          <div className="flex items-center gap-2"><Megaphone size={17} className="text-amber-400" /><h2 className="font-semibold text-white">系统公告</h2></div>
          <div className="mt-4 space-y-3">
            {announcements.length ? announcements.slice(0, 4).map((item) => (
              <article key={item.id} className="rounded-xl border border-white/5 bg-black/10 p-3">
                <h3 className="text-sm font-semibold text-slate-200">{item.title}</h3>
                <p className="mt-2 line-clamp-2 text-xs leading-5 text-slate-500">{item.content}</p>
                <p className="mt-2 text-[10px] text-slate-700">{new Date(item.publishedAt).toLocaleDateString()}</p>
              </article>
            )) : <p className="py-8 text-center text-sm text-slate-600">暂无公告</p>}
          </div>
        </div>
      </section>

      {popup && (
        <div className="fixed inset-0 z-50 grid place-items-center bg-black/70 p-4 backdrop-blur-sm">
          <div className="glass-card w-full max-w-lg rounded-3xl p-6">
            <div className="flex items-center gap-3"><span className="grid h-10 w-10 place-items-center rounded-xl bg-amber-400/10 text-amber-400"><Activity /></span><div><p className="text-xs text-amber-400">系统公告</p><h2 className="font-bold text-white">{popup.title}</h2></div></div>
            <p className="mt-5 whitespace-pre-wrap text-sm leading-7 text-slate-300">{popup.content}</p>
            <button onClick={dismissPopup} className="gold-button mt-6 w-full rounded-xl px-4 py-3 font-bold">我知道了</button>
          </div>
        </div>
      )}
    </div>
  );
}
