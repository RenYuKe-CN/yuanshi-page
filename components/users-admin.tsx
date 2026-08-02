"use client";

import { useEffect, useState } from "react";
import { Plus, Trash2 } from "lucide-react";
import { api } from "@/components/api";

type UserItem = {
  id: string;
  username: string;
  role: "ADMIN" | "USER";
  isOwner: boolean;
  status: "ACTIVE" | "DISABLED";
  lastLoginAt: string | null;
  createdAt: string;
};

export function UsersAdmin() {
  const [users, setUsers] = useState<UserItem[]>([]);
  const [viewer, setViewer] = useState({ id: "", isOwner: false });
  const [form, setForm] = useState({ username: "", password: "", role: "USER", status: "ACTIVE" });
  const [error, setError] = useState("");
  const [recovery, setRecovery] = useState({ username: "", code: "" });

  async function load() {
    try {
      const data = await api<{ users: UserItem[]; viewer: { id: string; isOwner: boolean } }>("/api/users");
      setUsers(data.users);
      setViewer(data.viewer);
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "读取失败");
    }
  }

  async function create(event: React.FormEvent) {
    event.preventDefault();
    try {
      const data = await api<{ user: UserItem; recoveryCode: string }>("/api/users", { method: "POST", body: JSON.stringify(form) });
      setRecovery({ username: data.user.username, code: data.recoveryCode });
      setForm({ username: "", password: "", role: "USER", status: "ACTIVE" });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "创建失败");
    }
  }

  async function update(id: string, patch: Partial<UserItem>) {
    await api(`/api/users/${id}`, { method: "PATCH", body: JSON.stringify(patch) });
    await load();
  }

  async function remove(user: UserItem) {
    if (!window.confirm(`确认删除账号 ${user.username}？历史查询和操作日志会保留。`)) return;
    await api(`/api/users/${user.id}`, { method: "DELETE" });
    await load();
  }

  useEffect(() => {
    load();
  }, []);

  return (
    <div className="space-y-4">
      {recovery.code && (
        <div className="rounded-2xl border border-amber-400/25 bg-amber-400/10 p-4 text-sm text-amber-100">
          账号 <strong>{recovery.username}</strong> 已创建。请立即保存并交给本人，恢复码只显示这一次：
          <div className="mt-2 break-all rounded-xl border border-amber-400/20 bg-black/25 p-3 font-mono text-amber-200">{recovery.code}</div>
        </div>
      )}
      <form onSubmit={create} className="glass-card grid gap-3 rounded-3xl p-4 md:grid-cols-[1fr_1fr_150px_140px_auto]">
        <input placeholder="用户名（支持中文）" minLength={3} maxLength={40} required value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })} className="dark-input rounded-xl px-4 py-3 text-sm" />
        <input placeholder="初始密码（至少 10 位）" minLength={10} maxLength={128} required type="password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} className="dark-input rounded-xl px-4 py-3 text-sm" />
        <select value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })} className="dark-input rounded-xl px-3 py-3 text-sm">
          <option value="USER">普通用户</option>
          {viewer.isOwner && <option value="ADMIN">备用管理员</option>}
        </select>
        <select value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value })} className="dark-input rounded-xl px-3 py-3 text-sm">
          <option value="ACTIVE">启用</option>
          <option value="DISABLED">禁用</option>
        </select>
        <button className="gold-button inline-flex items-center justify-center gap-2 rounded-xl px-5 py-3 text-sm font-black">
          <Plus size={15} />
          新增
        </button>
      </form>
      {error && <div className="rounded-2xl border border-red-400/20 bg-red-400/5 px-4 py-3 text-sm text-red-300">{error}</div>}
      <section className="glass-card rounded-3xl">
        <div className="overflow-x-auto">
          <table className="luxury-table w-full min-w-[760px] text-left text-sm">
            <thead className="border-b border-white/5">
              <tr>
                <th className="p-4">用户名</th>
                <th className="p-4">角色</th>
                <th className="p-4">状态</th>
                <th className="p-4">最后登录</th>
                <th className="p-4">创建时间</th>
                <th className="p-4">操作</th>
              </tr>
            </thead>
            <tbody>
              {users.map((user) => (
                <tr key={user.id} className="border-b border-white/5 last:border-0">
                  <td className="p-4 font-semibold text-white">{user.username}</td>
                  <td className="p-4 text-slate-300">{user.isOwner ? "总管理员" : user.role === "ADMIN" ? "备用管理员" : "普通用户"}</td>
                  <td className="p-3">
                    {user.id === viewer.id || user.isOwner || (!viewer.isOwner && user.role === "ADMIN") ? (
                      <span className={user.status === "ACTIVE" ? "text-emerald-300" : "text-red-300"}>{user.status === "ACTIVE" ? "启用" : "禁用"}</span>
                    ) : (
                      <select value={user.status} onChange={(e) => update(user.id, { status: e.target.value as UserItem["status"] })} className="dark-input rounded-lg px-2 py-1">
                        <option value="ACTIVE">启用</option>
                        <option value="DISABLED">禁用</option>
                      </select>
                    )}
                  </td>
                  <td className="p-4 text-slate-400">{user.lastLoginAt ? new Date(user.lastLoginAt).toLocaleString() : "-"}</td>
                  <td className="p-4 text-slate-400">{new Date(user.createdAt).toLocaleString()}</td>
                  <td className="p-4">
                    {user.id === viewer.id || user.isOwner || (!viewer.isOwner && user.role === "ADMIN") ? (
                      <span className="text-xs text-slate-500">受保护</span>
                    ) : (
                      <button onClick={() => remove(user)} className="inline-flex items-center gap-1 rounded-lg border border-red-400/20 bg-red-400/10 px-2.5 py-1.5 text-xs font-bold text-red-300">
                        <Trash2 size={13} />删除
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
