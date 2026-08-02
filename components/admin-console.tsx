"use client";

import { useEffect, useState } from "react";
import { BadgeDollarSign, BellRing, Building2, CreditCard, Database, Laptop, RefreshCw, Users } from "lucide-react";
import { api } from "@/components/api";
import { AnalyticsPanel } from "@/components/analytics-panel";

type Overview = {
  plans: Array<{ id: string; code: string; name: string; priceUsd: string; queryLimit: number | null; active: boolean }>;
  users: Array<{ id: string; username: string; email: string | null; role: string; status: string; membership: { status: string; queryLimit: number | null; queryUsed: number; expiresAt: string | null; plan: { code: string; name: string } } | null }>;
  orders: Array<{ id: string; orderNo: string; status: string; amount: string; paymentToken: string; txHash: string | null; createdAt: string; user: { username: string }; plan: { name: string } }>;
  devices: Array<{ id: string; deviceId: string; browser: string | null; os: string | null; status: string; boundAt: string | null; lastSeenAt: string; user: { username: string } }>;
  exchanges: Array<{ id: string; name: string; category: string; active: boolean }>;
  announcements: Array<{ id: string; title: string; content: string; type: string; active: boolean; popup: boolean; publishedAt: string }>;
};

const tabs = [
  ["analytics", "经营数据", Database],
  ["members", "会员管理", Users],
  ["orders", "订单管理", CreditCard],
  ["plans", "套餐管理", BadgeDollarSign],
  ["devices", "设备管理", Laptop],
  ["exchanges", "交易所管理", Building2],
  ["announcements", "公告管理", BellRing]
] as const;

export function AdminConsole() {
  const [data, setData] = useState<Overview | null>(null);
  const [tab, setTab] = useState<(typeof tabs)[number][0]>("analytics");
  const [message, setMessage] = useState("");
  const [exchangeForm, setExchangeForm] = useState({ name: "", category: "CEX" });
  const [noticeForm, setNoticeForm] = useState({ title: "", content: "", type: "NOTICE", active: true, popup: true });

  async function load() {
    try {
      setData(await api<Overview>("/api/admin/overview"));
      setMessage("");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "读取失败");
    }
  }
  useEffect(() => { load(); }, []);

  async function patch(url: string, body: object) {
    try {
      await api(url, { method: "PATCH", body: JSON.stringify(body) });
      await load();
      setMessage("操作成功");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "操作失败");
    }
  }

  async function setMembership(userId: string, planCode: "FREE" | "STARSHIP" | "PRO") {
    const expiresAt = planCode === "FREE" ? null : (() => {
      const date = new Date();
      const day = date.getDate();
      date.setDate(1);
      date.setMonth(date.getMonth() + 1);
      const lastDay = new Date(date.getFullYear(), date.getMonth() + 1, 0).getDate();
      date.setDate(Math.min(day, lastDay));
      return date.toISOString();
    })();
    await patch(`/api/admin/memberships/${userId}`, {
      planCode,
      status: planCode === "FREE" ? "FREE" : "ACTIVE",
      queryLimit: planCode === "PRO" ? null : planCode === "STARSHIP" ? 10 : 0,
      queryUsed: 0,
      expiresAt
    });
  }

  async function createExchange(event: React.FormEvent) {
    event.preventDefault();
    await api("/api/admin/exchanges", { method: "POST", body: JSON.stringify(exchangeForm) });
    setExchangeForm({ name: "", category: "CEX" });
    await load();
  }

  async function createNotice(event: React.FormEvent) {
    event.preventDefault();
    await api("/api/announcements", { method: "POST", body: JSON.stringify(noticeForm) });
    setNoticeForm({ title: "", content: "", type: "NOTICE", active: true, popup: true });
    await load();
  }

  return (
    <div className="space-y-6">
      <header className="flex items-end justify-between gap-4">
        <div><p className="text-xs font-semibold tracking-[.24em] text-amber-400">ADMIN CONSOLE</p><h1 className="mt-2 text-2xl font-bold text-white">管理后台</h1><p className="mt-2 text-sm text-slate-500">会员、订单、设备、交易所与公告统一管理。</p></div>
        <button onClick={load} className="inline-flex items-center gap-2 rounded-xl border border-white/10 px-4 py-2 text-sm text-slate-400"><RefreshCw size={15} />刷新</button>
      </header>
      <div className="flex gap-2 overflow-x-auto pb-1">
        {tabs.map(([key, label, Icon]) => <button key={key} onClick={() => setTab(key)} className={`inline-flex min-w-fit items-center gap-2 rounded-xl border px-4 py-2 text-sm ${tab === key ? "border-amber-400/30 bg-amber-400/10 text-amber-300" : "border-white/5 text-slate-500"}`}><Icon size={15} />{label}</button>)}
      </div>
      {message && <div className="rounded-xl border border-amber-400/20 bg-amber-400/5 px-4 py-3 text-sm text-amber-200">{message}</div>}

      {tab === "analytics" && <AnalyticsPanel />}
      {tab === "members" && <DataTable headers={["用户", "邮箱", "角色", "会员", "额度", "到期", "操作"]}>{data?.users.map((user) => <tr key={user.id} className="border-b border-white/5"><Cell>{user.username}</Cell><Cell>{user.email || "-"}</Cell><Cell>{user.role}</Cell><Cell>{user.membership?.plan.name || "普通用户"}</Cell><Cell>{user.membership?.queryLimit === null ? "无限" : `${user.membership?.queryUsed || 0}/${user.membership?.queryLimit || 0}`}</Cell><Cell>{user.membership?.expiresAt ? new Date(user.membership.expiresAt).toLocaleDateString() : "-"}</Cell><Cell><div className="flex gap-1"><Mini onClick={() => setMembership(user.id, "FREE")}>免费</Mini><Mini onClick={() => setMembership(user.id, "STARSHIP")}>星舰</Mini><Mini onClick={() => setMembership(user.id, "PRO")}>PRO</Mini></div></Cell></tr>)}</DataTable>}

      {tab === "orders" && <DataTable headers={["订单", "用户", "套餐", "金额", "状态", "交易 Hash", "时间"]}>{data?.orders.map((order) => <tr key={order.id} className="border-b border-white/5"><Cell>{order.orderNo}</Cell><Cell>{order.user.username}</Cell><Cell>{order.plan.name}</Cell><Cell>{order.amount} {order.paymentToken}</Cell><Cell><Status value={order.status} /></Cell><Cell><span className="block max-w-44 truncate font-mono text-xs">{order.txHash || "-"}</span></Cell><Cell>{new Date(order.createdAt).toLocaleString()}</Cell></tr>)}</DataTable>}

      {tab === "plans" && <div className="grid gap-4 md:grid-cols-3">{data?.plans.map((plan) => <div key={plan.id} className="glass-card rounded-2xl p-5"><h2 className="font-bold text-white">{plan.name}</h2><label className="mt-4 block text-xs text-slate-500">价格（USDT/USDC）<input defaultValue={plan.priceUsd} type="number" step="0.1" className="dark-input mt-2 w-full rounded-xl px-3 py-2 text-sm" onBlur={(e) => patch(`/api/admin/plans/${plan.id}`, { priceUsd: Number(e.target.value) })} /></label><label className="mt-3 block text-xs text-slate-500">查询次数（PRO 留空表示无限）<input defaultValue={plan.queryLimit ?? ""} type="number" className="dark-input mt-2 w-full rounded-xl px-3 py-2 text-sm" onBlur={(e) => patch(`/api/admin/plans/${plan.id}`, { queryLimit: e.target.value ? Number(e.target.value) : null })} /></label></div>)}</div>}

      {tab === "devices" && <DataTable headers={["用户", "设备", "浏览器/系统", "状态", "绑定", "最后出现", "操作"]}>{data?.devices.map((device) => <tr key={device.id} className="border-b border-white/5"><Cell>{device.user.username}</Cell><Cell><span className="block max-w-32 truncate font-mono text-xs">{device.deviceId}</span></Cell><Cell>{device.browser || "-"} / {device.os || "-"}</Cell><Cell><Status value={device.status} /></Cell><Cell>{device.boundAt ? new Date(device.boundAt).toLocaleString() : "-"}</Cell><Cell>{new Date(device.lastSeenAt).toLocaleString()}</Cell><Cell><div className="flex gap-1"><Mini onClick={() => patch(`/api/admin/devices/${device.id}`, { action: "UNBIND" })}>解绑</Mini><Mini onClick={() => patch(`/api/admin/devices/${device.id}`, { action: "BLOCK" })}>封禁</Mini><Mini onClick={() => patch(`/api/admin/devices/${device.id}`, { action: "ACTIVATE" })}>恢复</Mini></div></Cell></tr>)}</DataTable>}

      {tab === "exchanges" && <div className="space-y-4"><form onSubmit={createExchange} className="glass-card grid gap-3 rounded-2xl p-4 md:grid-cols-[1fr_160px_auto]"><input required value={exchangeForm.name} onChange={(e) => setExchangeForm({ ...exchangeForm, name: e.target.value })} placeholder="交易所名称" className="dark-input rounded-xl px-4 py-2 text-sm" /><select value={exchangeForm.category} onChange={(e) => setExchangeForm({ ...exchangeForm, category: e.target.value })} className="dark-input rounded-xl px-3 py-2 text-sm"><option value="CEX">CEX</option><option value="DEX">DEX</option><option value="OTHER">其他</option></select><button className="gold-button rounded-xl px-5 py-2 text-sm font-bold">新增交易所</button></form><DataTable headers={["名称", "类别", "状态", "操作"]}>{data?.exchanges.map((exchange) => <tr key={exchange.id} className="border-b border-white/5"><Cell>{exchange.name}</Cell><Cell>{exchange.category}</Cell><Cell>{exchange.active ? "启用" : "停用"}</Cell><Cell><Mini onClick={() => patch(`/api/admin/exchanges/${exchange.id}`, { active: !exchange.active })}>{exchange.active ? "停用" : "启用"}</Mini></Cell></tr>)}</DataTable></div>}

      {tab === "announcements" && <div className="space-y-4"><form onSubmit={createNotice} className="glass-card space-y-3 rounded-2xl p-5"><div className="grid gap-3 md:grid-cols-[1fr_180px]"><input required value={noticeForm.title} onChange={(e) => setNoticeForm({ ...noticeForm, title: e.target.value })} placeholder="公告标题" className="dark-input rounded-xl px-4 py-2 text-sm" /><select value={noticeForm.type} onChange={(e) => setNoticeForm({ ...noticeForm, type: e.target.value })} className="dark-input rounded-xl px-3 py-2 text-sm"><option value="NOTICE">公告</option><option value="MAINTENANCE">维护</option><option value="UPDATE">更新</option><option value="ACTIVITY">活动</option></select></div><textarea required value={noticeForm.content} onChange={(e) => setNoticeForm({ ...noticeForm, content: e.target.value })} placeholder="公告内容" rows={4} className="dark-input w-full rounded-xl px-4 py-3 text-sm" /><label className="flex gap-2 text-sm text-slate-400"><input type="checkbox" checked={noticeForm.popup} onChange={(e) => setNoticeForm({ ...noticeForm, popup: e.target.checked })} />登录后自动弹窗</label><button className="gold-button rounded-xl px-5 py-2 text-sm font-bold">发布公告</button></form><DataTable headers={["标题", "类型", "弹窗", "状态", "发布时间"]}>{data?.announcements.map((item) => <tr key={item.id} className="border-b border-white/5"><Cell>{item.title}</Cell><Cell>{item.type}</Cell><Cell>{item.popup ? "是" : "否"}</Cell><Cell>{item.active ? "发布中" : "已停用"}</Cell><Cell>{new Date(item.publishedAt).toLocaleString()}</Cell></tr>)}</DataTable></div>}
    </div>
  );
}

function DataTable({ headers, children }: { headers: string[]; children: React.ReactNode }) {
  return <div className="glass-card overflow-hidden rounded-2xl"><div className="overflow-x-auto"><table className="w-full min-w-[880px] text-left text-sm"><thead className="border-b border-white/5 bg-white/[.025] text-xs text-slate-600"><tr>{headers.map((item) => <th key={item} className="px-4 py-3 font-medium">{item}</th>)}</tr></thead><tbody>{children}</tbody></table></div></div>;
}
function Cell({ children }: { children: React.ReactNode }) { return <td className="px-4 py-3 text-slate-300">{children}</td>; }
function Mini({ children, onClick }: { children: React.ReactNode; onClick: () => void }) { return <button onClick={onClick} className="rounded-lg border border-white/10 px-2 py-1 text-xs text-slate-400 hover:border-amber-400/30 hover:text-amber-300">{children}</button>; }
function Status({ value }: { value: string }) { return <span className={`rounded-full px-2 py-1 text-xs ${value === "PAID" || value === "ACTIVE" ? "bg-emerald-400/10 text-emerald-300" : value === "REJECTED" || value === "BLOCKED" ? "bg-red-400/10 text-red-300" : "bg-amber-400/10 text-amber-300"}`}>{value}</span>; }
