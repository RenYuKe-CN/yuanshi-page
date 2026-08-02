"use client";

import Link from "next/link";
import { useState } from "react";
import { api } from "@/components/api";
import { EMAIL_DOMAIN_OPTIONS } from "@/lib/email-domains";

function splitEmail(email: string) {
  const selected = EMAIL_DOMAIN_OPTIONS.find((suffix) => email.toLowerCase().endsWith(suffix));
  if (!selected) return { local: email.includes("@") ? email.split("@")[0] : email, domain: "@gmail.com" };
  return { local: email.slice(0, -selected.length), domain: selected };
}

export default function RegisterPage() {
  const [form, setForm] = useState({ username: "", email: "", password: "", confirmPassword: "", acceptedStatement: false });
  const [error, setError] = useState("");
  const [recoveryCode, setRecoveryCode] = useState("");
  const [loading, setLoading] = useState(false);
  const emailParts = splitEmail(form.email);

  function setEmail(local: string, domain = emailParts.domain) {
    setForm({ ...form, email: local ? `${local.trim()}${domain}` : "" });
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError("");
    try {
      const data = await api<{ recoveryCode: string }>("/api/auth/register", {
        method: "POST",
        body: JSON.stringify(form)
      });
      setRecoveryCode(data.recoveryCode);
    } catch (err) {
      setError(err instanceof Error ? err.message : "注册失败");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-950 bg-cover bg-center p-4" style={{ backgroundImage: "linear-gradient(90deg, rgba(2,10,22,.48), rgba(2,10,22,.86)), url('/brand/crypto-background.jpg')" }}>
      <section className="w-full max-w-md rounded-2xl border border-amber-500/60 bg-slate-950/90 p-7 text-white shadow-2xl backdrop-blur">
        <div className="mb-6 flex items-center gap-3">
          <img src="/brand/ck-logo.jpg" alt="CK原石图标" className="h-14 w-14 rounded-2xl border border-amber-400 object-cover" />
          <div><h1 className="text-lg font-bold">创建账号</h1><p className="text-sm text-slate-400">注册后即可进入系统，开通会员后使用查重服务</p></div>
        </div>
        {recoveryCode ? (
          <div>
            <div className="rounded border border-emerald-700 bg-emerald-950/60 p-3 text-sm text-emerald-200">注册成功，请立即保存恢复码。</div>
            <div className="my-4 break-all rounded border border-amber-500 bg-slate-900 p-4 font-mono text-amber-300">{recoveryCode}</div>
            <p className="mb-4 text-xs text-slate-400">恢复码只显示一次，遗忘密码时必须使用。</p>
            <Link href="/login" className="block rounded bg-amber-500 px-4 py-2 text-center font-semibold text-slate-950">返回登录</Link>
          </div>
        ) : (
          <form onSubmit={submit} className="space-y-4">
            <input required minLength={3} maxLength={40} placeholder="用户名（支持中文）" value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })} className="dark-input w-full rounded-xl px-4 py-3 text-sm" />
            <div>
              <div className="grid grid-cols-[1fr_145px] overflow-hidden rounded-xl border border-white/10 bg-black/20 focus-within:border-amber-400/60 focus-within:ring-4 focus-within:ring-amber-400/10">
                <input required maxLength={180} placeholder="邮箱账号" value={emailParts.local} onChange={(e) => setEmail(e.target.value)} className="bg-transparent px-4 py-3 text-sm text-white outline-none" />
                <select value={emailParts.domain} onChange={(e) => setEmail(emailParts.local, e.target.value)} className="border-l border-white/10 bg-slate-950/80 px-3 text-sm font-bold text-amber-200 outline-none">
                  {EMAIL_DOMAIN_OPTIONS.map((domain) => <option key={domain} value={domain}>{domain}</option>)}
                </select>
              </div>
              <p className="mt-2 text-xs leading-5 text-slate-500">必须使用指定主流邮箱：Gmail、QQ邮箱、Outlook、163、iCloud、Yahoo、Proton、阿里云邮箱、Zoho Mail。</p>
            </div>
            <input required minLength={10} maxLength={128} type="password" placeholder="密码（至少 10 位）" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} className="dark-input w-full rounded-xl px-4 py-3 text-sm" />
            <input required minLength={10} maxLength={128} type="password" placeholder="再次输入密码" value={form.confirmPassword} onChange={(e) => setForm({ ...form, confirmPassword: e.target.value })} className="dark-input w-full rounded-xl px-4 py-3 text-sm" />
            <label className="flex items-start gap-2 text-sm text-slate-300">
              <input required type="checkbox" checked={form.acceptedStatement} onChange={(e) => setForm({ ...form, acceptedStatement: e.target.checked })} className="mt-1" />
              <span>我已阅读并同意 <Link href="/statement" target="_blank" className="font-semibold text-amber-400">《原石金手指 · 用户注册声明》</Link></span>
            </label>
            {error && <div className="rounded border border-red-700 bg-red-950/60 p-3 text-sm text-red-200">{error}</div>}
            <button disabled={loading || !form.acceptedStatement} className="w-full rounded bg-gradient-to-r from-amber-600 to-amber-400 px-4 py-2 font-semibold text-slate-950 disabled:opacity-60">{loading ? "注册中..." : "注册"}</button>
            <div className="flex justify-between text-sm text-amber-400"><Link href="/login">返回登录</Link><Link href="/recover">忘记密码</Link></div>
          </form>
        )}
      </section>
    </main>
  );
}
