"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import {
  Activity, BadgeDollarSign, CircleUserRound, Contact, Database,
  FileClock, Gauge, LogOut, Settings, ShieldCheck, Users
} from "lucide-react";

const mainNav = [
  { href: "/", label: "控制台", icon: Gauge },
  { href: "/ip-query", label: "IP 查重", icon: Activity },
  { href: "/history", label: "查询历史", icon: Database },
  { href: "/membership", label: "会员中心", icon: BadgeDollarSign },
  { href: "/profile", label: "用户中心", icon: CircleUserRound },
  { href: "/contact", label: "联系客服", icon: Contact }
];

const adminNav = [
  { href: "/users", label: "用户管理", icon: Users },
  { href: "/admin", label: "管理后台", icon: ShieldCheck },
  { href: "/logs", label: "系统日志", icon: FileClock },
  { href: "/settings", label: "系统设置", icon: Settings }
];

const businessItems = [
  ["⛁", "EFTT新增"],
  ["⌕", "交易所流动性提供"],
  ["◇", "流动性策略"],
  ["▣", "BD保职 & BD入职"],
  ["▤", "项目社区运营"],
  ["◎", "推特运营"],
  ["❉", "客户留存"],
  ["⬡", "合约量化开发"],
  ["◷", "后续直播、转化等业务"]
];

type Me = {
  username: string;
  role: "ADMIN" | "USER";
  isOwner: boolean;
};

export function Shell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [me, setMe] = useState<Me | null>(null);
  const [reminder, setReminder] = useState("");

  useEffect(() => {
    fetch("/api/auth/me")
      .then((response) => response.json())
      .then((data) => {
        setMe(data.user || null);
        setReminder(data.reminder || "");
      })
      .catch(() => setMe(null));
  }, []);

  async function logout() {
    await fetch("/api/auth/logout", { method: "POST" });
    router.push("/login");
  }

  function NavItem({ item }: { item: (typeof mainNav)[number] }) {
    const Icon = item.icon;
    const active = pathname === item.href;
    return (
      <Link
        href={item.href}
        className={`group flex min-w-fit items-center gap-3 rounded-xl px-3 py-2.5 text-sm transition ${
          active
            ? "border border-amber-400/30 bg-amber-400/10 text-amber-300 shadow-[inset_0_0_20px_rgba(251,191,36,.06)]"
            : "border border-transparent text-slate-400 hover:border-white/5 hover:bg-white/5 hover:text-white"
        }`}
      >
        <Icon size={17} className={active ? "text-amber-300" : "text-slate-500 group-hover:text-amber-300"} />
        {item.label}
      </Link>
    );
  }

  return (
    <div className="min-h-screen bg-[#05080f] text-slate-100 lg:flex">
      <aside className="relative border-b border-white/10 bg-[#07101c]/95 shadow-[24px_0_90px_rgba(0,0,0,.34)] backdrop-blur-xl before:pointer-events-none before:absolute before:inset-0 before:bg-[radial-gradient(circle_at_50%_0%,rgba(245,196,81,.12),transparent_18rem)] lg:sticky lg:top-0 lg:h-screen lg:w-72 lg:overflow-y-auto lg:border-b-0 lg:border-r lg:border-amber-400/10">
        <div className="relative m-4 flex h-[5.5rem] items-center gap-3 rounded-[1.6rem] border border-amber-400/12 bg-white/[.035] px-4 shadow-[inset_0_1px_rgba(255,255,255,.07)]">
          <img src="/brand/ck-logo.jpg" alt="CK原石图标" className="h-14 w-14 rounded-2xl border border-amber-400/60 object-cover shadow-[0_0_32px_rgba(245,158,11,.18)]" />
          <div>
            <div className="text-lg font-black tracking-[-.04em] text-white">原石金手指</div>
            <div className="mt-1 text-[10px] font-black tracking-[.24em] text-amber-400">IP RISK INTELLIGENCE</div>
          </div>
        </div>

        <nav className="relative flex gap-1 overflow-x-auto p-3 lg:block lg:space-y-2">
          {mainNav.map((item) => <NavItem key={item.href} item={item} />)}
          {me?.isOwner && (
            <>
              <div className="hidden px-3 pb-2 pt-5 text-[10px] font-black tracking-[.22em] text-slate-600 lg:block">ADMIN CONSOLE</div>
              {adminNav.map((item) => <NavItem key={item.href} item={item} />)}
            </>
          )}
        </nav>

        <section className="relative hidden border-t border-amber-400/10 px-3 py-5 lg:block">
          <div className="mb-3 px-2 text-xs font-black tracking-wider text-amber-400">核心业务矩阵</div>
          <div className="space-y-1.5">
            {businessItems.map(([icon, label]) => (
              <div key={label} className="group flex items-center gap-2.5 rounded-2xl border border-white/10 bg-white/[.025] px-3 py-2.5 text-xs font-bold text-slate-300 shadow-[inset_0_1px_rgba(255,255,255,.04)] transition hover:border-amber-400/25 hover:bg-amber-400/5 hover:text-white">
                <span className="inline-grid h-8 w-8 shrink-0 place-items-center rounded-xl border border-amber-400/35 bg-amber-400/10 text-amber-400 transition group-hover:scale-105">{icon}</span>
                <span className="tracking-[-.01em]">{label}</span>
              </div>
            ))}
          </div>
        </section>

        {me && (
          <div className="relative hidden border-t border-white/5 p-4 lg:block">
            <div className="mb-3 rounded-2xl border border-white/5 bg-white/[.035] px-3 py-2 text-xs text-slate-400">
              <span className="font-semibold text-white">{me.username}</span>
              <span className="ml-2 text-amber-400">{me.isOwner ? "总管理员" : me.role === "ADMIN" ? "备用管理员" : "普通用户"}</span>
            </div>
            <button onClick={logout} className="flex w-full items-center gap-2 rounded-xl px-3 py-2 text-sm text-slate-400 transition hover:bg-red-500/10 hover:text-red-300">
              <LogOut size={16} />退出登录
            </button>
          </div>
        )}
      </aside>

      <main className="flex min-h-screen flex-1 flex-col overflow-hidden">
        {reminder && <div className="border-b border-amber-400/20 bg-amber-400/10 px-5 py-2 text-center text-xs font-semibold text-amber-300">{reminder}</div>}
        <div className="flex-1 p-4 md:p-6 lg:p-8 xl:p-10">{children}</div>
        <footer className="mx-4 border-t border-white/5 py-5 text-center text-xs text-slate-600">
          产品由 CK原石提供技术支持 ➡️TG{" "}
          <a className="font-semibold text-amber-400 hover:text-amber-300" href="https://t.me/mommo10338" target="_blank" rel="noopener noreferrer">@mommo10338</a>
          <span className="mx-3">·</span>
          技术业务交流群：
          <a className="font-semibold text-amber-400 hover:text-amber-300" href="https://t.me/B132609" target="_blank" rel="noopener noreferrer">加入 Telegram</a>
        </footer>
      </main>
    </div>
  );
}
