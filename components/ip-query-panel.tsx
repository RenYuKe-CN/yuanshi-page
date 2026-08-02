"use client";

import { useState } from "react";
import { Search, CheckCircle2, XCircle } from "lucide-react";
import { api } from "@/components/api";
import { SIMILARITY_LABELS } from "@/lib/constants";
import { ExchangeName, ExchangePicker } from "@/components/exchange-picker";
import Link from "next/link";

type Similarity = {
  id: string;
  fullIp: string;
  exchange: string;
  username: string;
  queryCount: number;
  firstSeenAt: string;
  lastSeenAt: string;
  similarity: number;
  matchA: boolean;
  matchB: boolean;
  matchC: boolean;
  matchD: boolean;
};

type QueryResult = {
  current: { fullIp: string; exchange: string; segmentA: number; segmentB: number; segmentC: number; segmentD: number };
  exactDuplicate: boolean;
  topSimilarity: number;
  bestMatch: Similarity | null;
  similarities: Similarity[];
};

function MatchCell({ label, ok }: { label: string; ok: boolean }) {
  const Icon = ok ? CheckCircle2 : XCircle;
  return (
    <span className={`inline-flex items-center gap-1 rounded-lg border px-2 py-1 text-xs ${ok ? "border-emerald-400/20 bg-emerald-400/10 text-emerald-300" : "border-white/10 bg-white/5 text-slate-600"}`}>
      <Icon size={13} />
      {label}
    </span>
  );
}

export function IpQueryPanel() {
  const [ip, setIp] = useState("");
  const [exchange, setExchange] = useState("");
  const [result, setResult] = useState<QueryResult | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (loading) return;
    if (!exchange) {
      setError("请选择交易所");
      return;
    }
    setLoading(true);
    setError("");
    try {
      const data = await api<QueryResult>("/api/ip/query", {
        method: "POST",
        body: JSON.stringify({ ip, exchange })
      });
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "查询失败");
    } finally {
      setLoading(false);
    }
  }

  const score = result?.topSimilarity ?? 0;

  return (
    <div className="space-y-5">
      <section className="glass-card rounded-2xl p-5">
        <form onSubmit={submit} className="grid gap-3 md:grid-cols-[1fr_220px_auto]">
          <input
            value={ip}
            onChange={(e) => setIp(e.target.value)}
            placeholder="输入 IPv4，例如 192.168.1.10"
            className="dark-input rounded-xl px-4 py-3"
          />
          <ExchangePicker value={exchange} onChange={setExchange} />
          <button disabled={loading || !exchange} className="gold-button inline-flex items-center justify-center gap-2 rounded-xl px-5 py-3 font-bold disabled:opacity-50">
            <Search size={16} />
            {loading ? "查询中..." : "查询"}
          </button>
        </form>
        {error && <div className="mt-3 rounded-xl border border-red-400/20 bg-red-400/5 px-4 py-3 text-sm text-red-300">{error}{(error.includes("会员") || error.includes("额度")) && <div className="mt-3 flex gap-2"><Link href="/membership" className="rounded-lg bg-amber-400 px-3 py-2 text-xs font-bold text-slate-950">立即开通</Link><Link href="/contact" className="rounded-lg border border-white/10 px-3 py-2 text-xs text-slate-300">联系客服</Link></div>}</div>}
      </section>

      {result && (
        <section className="grid gap-5 lg:grid-cols-[280px_1fr]">
          <div className={`rounded border p-5 status-${score}`}>
            <div className="text-sm opacity-80">最高相似度</div>
            <div className="mt-2 text-5xl font-bold">{score}%</div>
            <div className="mt-2 text-sm">{SIMILARITY_LABELS[score] || "相似记录"}</div>
            <div className="mt-5 space-y-2 text-sm">
              <div>当前 IP：{result.current.fullIp}</div>
              <div className="flex items-center gap-1">交易所：<ExchangeName name={result.current.exchange} /></div>
              <div>精确重复：{result.exactDuplicate ? "是" : "否"}</div>
            </div>
          </div>
          <div className="glass-card rounded-2xl p-5">
            <h2 className="mb-4 text-base font-bold">最相似历史记录</h2>
            {result.bestMatch ? (
              <div className="space-y-4">
                <div className="grid gap-3 text-sm md:grid-cols-3">
                  <div><span className="text-slate-500">历史 IP</span><br />{result.bestMatch.fullIp}</div>
                  <div><span className="text-slate-500">交易所</span><br /><ExchangeName name={result.bestMatch.exchange} /></div>
                  <div><span className="text-slate-500">查询次数</span><br />{result.bestMatch.queryCount}</div>
                  <div><span className="text-slate-500">录入用户</span><br />{result.bestMatch.username}</div>
                  <div><span className="text-slate-500">首次录入</span><br />{new Date(result.bestMatch.firstSeenAt).toLocaleString()}</div>
                  <div><span className="text-slate-500">最近查询</span><br />{new Date(result.bestMatch.lastSeenAt).toLocaleString()}</div>
                </div>
                <div className="flex flex-wrap gap-2">
                  <MatchCell label="A 段" ok={result.bestMatch.matchA} />
                  <MatchCell label="B 段" ok={result.bestMatch.matchB} />
                  <MatchCell label="C 段" ok={result.bestMatch.matchC} />
                  <MatchCell label="D 段" ok={result.bestMatch.matchD} />
                </div>
              </div>
            ) : (
              <p className="text-sm text-slate-500">暂无历史记录，本次查询已自动入库。</p>
            )}
          </div>
        </section>
      )}

      {result && (
        <section className="glass-card rounded-2xl p-5">
          <h2 className="mb-4 text-base font-bold">相似记录 Top 20</h2>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[860px] text-left text-sm">
              <thead className="border-b border-white/5 bg-white/[.025] text-slate-600">
                <tr>
                  <th className="p-3">相似度</th>
                  <th className="p-3">历史 IP</th>
                  <th className="p-3">交易所</th>
                  <th className="p-3">A/B/C/D</th>
                  <th className="p-3">录入用户</th>
                  <th className="p-3">首次录入</th>
                  <th className="p-3">最近查询</th>
                  <th className="p-3">次数</th>
                </tr>
              </thead>
              <tbody>
                {result.similarities.map((item) => (
                  <tr key={item.id} className="border-b border-white/5 last:border-0">
                    <td className="p-3"><span className={`rounded border px-2 py-1 status-${item.similarity}`}>{item.similarity}%</span></td>
                    <td className="p-3 font-mono">{item.fullIp}</td>
                    <td className="p-3"><ExchangeName name={item.exchange} /></td>
                    <td className="p-3">
                      <div className="flex gap-1">
                        <MatchCell label="A" ok={item.matchA} />
                        <MatchCell label="B" ok={item.matchB} />
                        <MatchCell label="C" ok={item.matchC} />
                        <MatchCell label="D" ok={item.matchD} />
                      </div>
                    </td>
                    <td className="p-3">{item.username}</td>
                    <td className="p-3">{new Date(item.firstSeenAt).toLocaleString()}</td>
                    <td className="p-3">{new Date(item.lastSeenAt).toLocaleString()}</td>
                    <td className="p-3">{item.queryCount}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </div>
  );
}
