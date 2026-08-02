"use client";

import Link from "next/link";
import { useState } from "react";
import { api } from "@/components/api";

export default function RecoverPage() {
  const [form, setForm] = useState({ username: "", recoveryCode: "", password: "", confirmPassword: "" });
  const [error, setError] = useState("");
  const [newCode, setNewCode] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError("");
    try {
      const data = await api<{ recoveryCode: string }>("/api/auth/recover", {
        method: "POST",
        body: JSON.stringify(form)
      });
      setNewCode(data.recoveryCode);
    } catch (err) {
      setError(err instanceof Error ? err.message : "密码重置失败");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-950 bg-cover bg-center p-4" style={{ backgroundImage: "linear-gradient(90deg, rgba(2,10,22,.48), rgba(2,10,22,.86)), url('/brand/crypto-background.jpg')" }}>
      <section className="w-full max-w-md rounded-2xl border border-amber-500/60 bg-slate-950/90 p-7 text-white shadow-2xl backdrop-blur">
        <h1 className="mb-1 text-xl font-bold">找回密码</h1>
        <p className="mb-6 text-sm text-slate-400">使用注册时保存的恢复码重置密码</p>
        {newCode ? (
          <div>
            <div className="rounded border border-emerald-700 bg-emerald-950/60 p-3 text-sm text-emerald-200">密码已重置，旧恢复码已经失效。</div>
            <div className="my-4 break-all rounded border border-amber-500 bg-slate-900 p-4 font-mono text-amber-300">{newCode}</div>
            <p className="mb-4 text-xs text-slate-400">请保存上面的新恢复码。</p>
            <Link href="/login" className="block rounded bg-amber-500 px-4 py-2 text-center font-semibold text-slate-950">使用新密码登录</Link>
          </div>
        ) : (
          <form onSubmit={submit} className="space-y-4">
            <input required placeholder="用户名" value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })} className="w-full rounded border border-slate-600 px-3 py-2 text-slate-900" />
            <input required placeholder="密码恢复码" value={form.recoveryCode} onChange={(e) => setForm({ ...form, recoveryCode: e.target.value })} className="w-full rounded border border-slate-600 px-3 py-2 text-slate-900" />
            <input required minLength={10} maxLength={128} type="password" placeholder="新密码（至少 10 位）" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} className="w-full rounded border border-slate-600 px-3 py-2 text-slate-900" />
            <input required minLength={10} maxLength={128} type="password" placeholder="再次输入新密码" value={form.confirmPassword} onChange={(e) => setForm({ ...form, confirmPassword: e.target.value })} className="w-full rounded border border-slate-600 px-3 py-2 text-slate-900" />
            {error && <div className="rounded border border-red-700 bg-red-950/60 p-3 text-sm text-red-200">{error}</div>}
            <button disabled={loading} className="w-full rounded bg-gradient-to-r from-amber-600 to-amber-400 px-4 py-2 font-semibold text-slate-950 disabled:opacity-60">{loading ? "处理中..." : "重置密码"}</button>
            <div className="flex justify-between text-sm text-amber-400"><Link href="/login">返回登录</Link><Link href="/register">注册账号</Link></div>
          </form>
        )}
        <div className="mt-6 border-t border-slate-700 pt-4 text-center text-xs text-slate-400">恢复码丢失请联系：产品由 CK原石提供技术支持 ➡️TG <a className="font-semibold text-amber-400" href="https://t.me/mommo10338" target="_blank" rel="noopener noreferrer">@mommo10338</a></div>
      </section>
    </main>
  );
}
