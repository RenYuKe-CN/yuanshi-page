"use client";

import { useEffect, useState } from "react";
import { Download, Trash2 } from "lucide-react";
import { api } from "@/components/api";
import { ExchangeName, ExchangePicker } from "@/components/exchange-picker";

type Item = {
  id: string;
  fullIp: string;
  segmentA: number;
  segmentB: number;
  segmentC: number;
  segmentD: number;
  exchange: string;
  lastSimilarity: number;
  queryCount: number;
  firstSeenAt: string;
  lastSeenAt: string;
  user: { id: string; username: string };
};

export function HistoryTable() {
  const [items, setItems] = useState<Item[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [filters, setFilters] = useState({ fullIp: "", segmentA: "", segmentB: "", segmentC: "", segmentD: "", exchange: "", similarity: "", userId: "", from: "", to: "" });
  const [error, setError] = useState("");

  async function load(nextPage = page) {
    const params = new URLSearchParams({ page: String(nextPage), pageSize: "20" });
    Object.entries(filters).forEach(([key, value]) => {
      if (value) params.set(key, value);
    });
    try {
      const data = await api<{ items: Item[]; total: number }>(`/api/history?${params}`);
      setItems(data.items);
      setTotal(data.total);
      setPage(nextPage);
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "读取失败");
    }
  }

  async function remove(id: string) {
    if (!confirm("确认删除这条记录？")) return;
    await api(`/api/history/${id}`, { method: "DELETE" });
    await load();
  }

  useEffect(() => {
    load(1);
    // 首次加载使用默认筛选；用户修改筛选后由“筛选”按钮显式触发。
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const pages = Math.max(1, Math.ceil(total / 20));
  const exportUrl = `/api/history/export?${new URLSearchParams(Object.entries(filters).filter(([, value]) => value))}`;
  const excelUrl = `${exportUrl}${exportUrl.includes("?") ? "&" : "?"}format=xlsx`;

  return (
    <div className="space-y-4">
      <section className="glass-card rounded-2xl p-4">
        <div className="grid gap-3 md:grid-cols-5">
          {(["fullIp", "segmentA", "segmentB", "segmentC", "segmentD"] as const).map((key) => (
            <input key={key} placeholder={key === "fullIp" ? "完整 IP" : key.replace("segment", "") + " 段"} value={filters[key]} onChange={(e) => setFilters({ ...filters, [key]: e.target.value })} className="dark-input rounded-xl px-3 py-2 text-sm" />
          ))}
          <ExchangePicker value={filters.exchange} onChange={(exchange) => setFilters({ ...filters, exchange })} allowAll />
          <select value={filters.similarity} onChange={(e) => setFilters({ ...filters, similarity: e.target.value })} className="dark-input rounded-xl px-3 py-2 text-sm">
            <option value="">全部重复率</option>
            {[100, 75, 50, 25, 0].map((item) => <option key={item} value={item}>{item}%</option>)}
          </select>
          <input placeholder="用户 ID" value={filters.userId} onChange={(e) => setFilters({ ...filters, userId: e.target.value })} className="dark-input rounded-xl px-3 py-2 text-sm" />
          <input type="date" value={filters.from} onChange={(e) => setFilters({ ...filters, from: e.target.value })} className="dark-input rounded-xl px-3 py-2 text-sm" />
          <input type="date" value={filters.to} onChange={(e) => setFilters({ ...filters, to: e.target.value })} className="dark-input rounded-xl px-3 py-2 text-sm" />
          <button onClick={() => load(1)} className="gold-button rounded-xl px-4 py-2 text-sm font-bold">筛选</button>
          <a href={exportUrl} className="inline-flex items-center justify-center gap-2 rounded-xl border border-white/10 px-4 py-2 text-sm text-slate-300">
            <Download size={15} />
            导出 CSV
          </a>
          <a href={excelUrl} className="inline-flex items-center justify-center gap-2 rounded-xl border border-white/10 px-4 py-2 text-sm text-slate-300"><Download size={15} />导出 Excel</a>
        </div>
        {error && <div className="mt-3 rounded-2xl border border-red-400/20 bg-red-400/5 px-4 py-3 text-sm text-red-300">{error}</div>}
      </section>

      <section className="glass-card rounded-3xl">
        <div className="overflow-x-auto">
          <table className="luxury-table w-full min-w-[900px] text-left text-sm">
            <thead className="border-b border-white/5">
              <tr>
                <th className="p-3">完整 IP</th>
                <th className="p-3">A/B/C/D</th>
                <th className="p-3">交易所</th>
                <th className="p-3">重复率</th>
                <th className="p-3">用户</th>
                <th className="p-3">查询次数</th>
                <th className="p-3">首次录入</th>
                <th className="p-3">最近查询</th>
                <th className="p-3">操作</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr key={item.id} className="border-b border-white/5 last:border-0">
                  <td className="p-3 font-mono">{item.fullIp}</td>
                  <td className="p-3">{item.segmentA}.{item.segmentB}.{item.segmentC}.{item.segmentD}</td>
                  <td className="p-3"><ExchangeName name={item.exchange} /></td>
                  <td className="p-3"><span className={`rounded border px-2 py-1 status-${item.lastSimilarity}`}>{item.lastSimilarity}%</span></td>
                  <td className="p-3">{item.user.username}</td>
                  <td className="p-3">{item.queryCount}</td>
                  <td className="p-3">{new Date(item.firstSeenAt).toLocaleString()}</td>
                  <td className="p-3">{new Date(item.lastSeenAt).toLocaleString()}</td>
                  <td className="p-3">
                    <button onClick={() => remove(item.id)} className="inline-flex items-center gap-1 rounded-lg border border-red-400/20 bg-red-400/10 px-2.5 py-1.5 text-xs font-bold text-red-300">
                      <Trash2 size={14} />
                      删除
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="flex items-center justify-between p-3 text-sm text-slate-500">
          <span>共 {total} 条，第 {page}/{pages} 页</span>
          <div className="flex gap-2">
            <button disabled={page <= 1} onClick={() => load(page - 1)} className="rounded-xl border border-white/10 bg-white/5 px-3 py-1 text-slate-300 disabled:opacity-40">上一页</button>
            <button disabled={page >= pages} onClick={() => load(page + 1)} className="rounded-xl border border-white/10 bg-white/5 px-3 py-1 text-slate-300 disabled:opacity-40">下一页</button>
          </div>
        </div>
      </section>
    </div>
  );
}
