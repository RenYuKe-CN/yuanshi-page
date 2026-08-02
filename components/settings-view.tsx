"use client";

import { useEffect, useState } from "react";
import { Globe2, KeyRound, SearchCheck } from "lucide-react";
import { api } from "@/components/api";

type Settings = {
  loginRateLimit: number;
  queryRateLimit: number;
  trustedOrigin: string;
};

export function SettingsView() {
  const [settings, setSettings] = useState<Settings | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api<{ settings: Settings }>("/api/settings")
      .then((data) => setSettings(data.settings))
      .catch((err) => setError(err instanceof Error ? err.message : "读取失败"));
  }, []);

  if (error) return <div className="rounded-2xl border border-red-400/20 bg-red-400/5 px-4 py-3 text-sm text-red-300">{error}</div>;
  if (!settings) return <div className="glass-card rounded-3xl p-8 text-sm text-slate-500">系统参数加载中...</div>;

  const cards = [
    { label: "登录限流", value: `${settings.loginRateLimit}/分钟`, icon: KeyRound, note: "防止暴力登录与撞库尝试" },
    { label: "查询限流", value: `${settings.queryRateLimit}/分钟`, icon: SearchCheck, note: "保护查重接口稳定运行" },
    { label: "可信来源", value: settings.trustedOrigin || "-", icon: Globe2, note: "生产部署域名 / Origin 白名单" }
  ];

  return (
    <section className="grid gap-4 md:grid-cols-3">
      {cards.map(({ label, value, icon: Icon, note }) => (
        <article key={label} className="glass-card rounded-3xl p-6">
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="text-xs font-black uppercase tracking-[.18em] text-slate-500">{label}</p>
              <p className="mt-3 break-all text-2xl font-black tracking-[-.04em] text-white">{value}</p>
            </div>
            <span className="grid h-11 w-11 shrink-0 place-items-center rounded-2xl border border-amber-400/20 bg-amber-400/10 text-amber-300">
              <Icon size={20} />
            </span>
          </div>
          <p className="mt-5 text-xs leading-5 text-slate-500">{note}</p>
        </article>
      ))}
    </section>
  );
}
