"use client";

import { useEffect, useState } from "react";
import { api } from "@/components/api";

type LogItem = {
  id: string;
  action: string;
  targetType: string;
  targetId: string | null;
  detail: unknown;
  ipAddress: string | null;
  createdAt: string;
  user: { username: string } | null;
};

export function LogsTable() {
  const [items, setItems] = useState<LogItem[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    api<{ items: LogItem[] }>("/api/logs")
      .then((data) => setItems(data.items))
      .catch((err) => setError(err instanceof Error ? err.message : "读取失败"));
  }, []);

  return (
    <section className="glass-card rounded-3xl">
      {error && <div className="m-4 rounded-2xl border border-red-400/20 bg-red-400/5 px-4 py-3 text-sm text-red-300">{error}</div>}
      <div className="overflow-x-auto">
        <table className="luxury-table w-full min-w-[900px] text-left text-sm">
          <thead className="border-b border-white/5">
            <tr>
              <th className="p-4">时间</th>
              <th className="p-4">用户</th>
              <th className="p-4">动作</th>
              <th className="p-4">对象</th>
              <th className="p-4">来源 IP</th>
              <th className="p-4">详情</th>
            </tr>
          </thead>
          <tbody>
            {items.map((item) => (
              <tr key={item.id} className="border-b border-white/5 last:border-0">
                <td className="p-4 text-slate-300">{new Date(item.createdAt).toLocaleString()}</td>
                <td className="p-4 font-semibold text-white">{item.user?.username || "-"}</td>
                <td className="p-4"><span className="rounded-full border border-amber-400/20 bg-amber-400/10 px-2.5 py-1 text-xs font-bold text-amber-200">{item.action}</span></td>
                <td className="p-4 text-slate-400">{item.targetType} {item.targetId || ""}</td>
                <td className="p-4 font-mono text-xs text-slate-400">{item.ipAddress || "-"}</td>
                <td className="max-w-[420px] truncate p-4 font-mono text-xs text-slate-500">{JSON.stringify(item.detail)}</td>
              </tr>
            ))}
            {!items.length && <tr><td colSpan={6} className="p-10 text-center text-sm text-slate-600">暂无操作日志</td></tr>}
          </tbody>
        </table>
      </div>
    </section>
  );
}
