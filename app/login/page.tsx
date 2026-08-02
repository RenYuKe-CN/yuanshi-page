"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { ArrowRight, LockKeyhole, UserRound } from "lucide-react";
import { api } from "@/components/api";
import { collectDeviceFingerprint } from "@/lib/client-device";
import { AuthBrandPanel } from "@/components/auth-brand-panel";
import { EMAIL_DOMAIN_OPTIONS } from "@/lib/email-domains";

function splitIdentifier(value: string) {
  const selected = EMAIL_DOMAIN_OPTIONS.find((suffix) => value.toLowerCase().endsWith(suffix));
  if (!selected) return { local: value.includes("@") ? value.split("@")[0] : value, domain: "" };
  return { local: value.slice(0, -selected.length), domain: selected };
}

export default function LoginPage() {
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const identifier = splitIdentifier(username);

  function setIdentifier(local: string, domain = identifier.domain) {
    setUsername(domain ? `${local.trim()}${domain}` : local);
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError("");
    try {
      const device = await collectDeviceFingerprint();
      await api("/api/auth/login", {
        method: "POST",
        body: JSON.stringify({ username, password, device })
      });
      router.push("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "登录失败");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="grid min-h-screen bg-[#070b12] lg:grid-cols-[1.05fr_.95fr]">
      <AuthBrandPanel />
      <section className="flex items-center justify-center p-5 md:p-10">
        <div className="w-full max-w-md">
          <div className="mb-8 lg:hidden"><div className="flex items-center gap-3"><img src="/brand/ck-logo.jpg" alt="CK原石图标" className="h-12 w-12 rounded-xl border border-amber-400/50 object-cover" /><div><h1 className="font-bold text-white">原石金手指</h1><p className="text-xs text-amber-400">IP 查重管理系统</p></div></div></div>
          <p className="text-xs font-semibold tracking-[.24em] text-amber-400">WELCOME BACK</p>
          <h2 className="mt-3 text-3xl font-bold text-white">登录您的账户</h2>
          <p className="mt-2 text-sm text-slate-500">使用管理员或普通用户账号继续。</p>
          <form onSubmit={submit} className="mt-8 space-y-4">
            <label className="block">
              <span className="mb-2 block text-xs font-medium text-slate-400">用户名 / 邮箱</span>
              <div className="dark-input grid grid-cols-[auto_1fr_145px] items-center overflow-hidden rounded-xl px-4 pr-0">
                <UserRound size={17} className="text-slate-600" />
                <input required autoComplete="username" className="w-full bg-transparent px-3 py-3.5 text-sm outline-none" value={identifier.local} onChange={(e) => setIdentifier(e.target.value)} placeholder="用户名或邮箱账号" />
                <select value={identifier.domain} onChange={(e) => setIdentifier(identifier.local, e.target.value)} className="h-full border-l border-white/10 bg-slate-950/70 px-2 text-xs font-bold text-amber-200 outline-none">
                  <option value="">用户名登录</option>
                  {EMAIL_DOMAIN_OPTIONS.map((domain) => <option key={domain} value={domain}>{domain}</option>)}
                </select>
              </div>
            </label>
            <label className="block"><span className="mb-2 block text-xs font-medium text-slate-400">密码</span><div className="dark-input flex items-center gap-3 rounded-xl px-4"><LockKeyhole size={17} className="text-slate-600" /><input required autoComplete="current-password" className="w-full bg-transparent py-3.5 text-sm outline-none" type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="请输入密码" /></div></label>
            {error && <div className="rounded-xl border border-red-400/20 bg-red-400/5 px-4 py-3 text-sm text-red-300">{error}</div>}
            <button disabled={loading} className="gold-button flex w-full items-center justify-center gap-2 rounded-xl px-4 py-3.5 font-bold disabled:opacity-50">{loading ? "安全登录中..." : "登录"}<ArrowRight size={17} /></button>
          </form>
          <div className="mt-5 flex justify-between text-sm"><Link href="/register" className="font-semibold text-amber-400 hover:text-amber-300">注册账号</Link><Link href="/recover" className="text-slate-500 hover:text-slate-300">忘记密码</Link></div>
          <div className="mt-10 border-t border-white/5 pt-5 text-xs leading-6 text-slate-600">
            产品由 CK原石提供技术支持 ➡️TG <a className="font-semibold text-amber-400" href="https://t.me/mommo10338" target="_blank" rel="noopener noreferrer">@mommo10338</a>
            <span className="mx-2">·</span>
            <a className="font-semibold text-amber-400" href="https://t.me/B132609" target="_blank" rel="noopener noreferrer">技术业务交流群</a>
          </div>
        </div>
      </section>
    </main>
  );
}
