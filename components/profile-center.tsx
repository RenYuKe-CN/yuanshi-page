"use client";

import { useEffect, useState } from "react";
import { CalendarClock, KeyRound, Laptop, LogOut, Shield, UserRound } from "lucide-react";
import { useRouter } from "next/navigation";
import { api } from "@/components/api";

type MeData = {
  user: { username: string; role: string; isOwner: boolean };
  membership: {
    planName: string;
    status: string;
    expiresAt: string | null;
    remaining: number | null;
    unlimited: boolean;
  };
  device: {
    deviceId: string;
    browser: string | null;
    os: string | null;
    status: string;
    boundAt: string | null;
    lastSeenAt: string;
  } | null;
};

export function ProfileCenter() {
  const router = useRouter();
  const [data, setData] = useState<MeData | null>(null);
  const [form, setForm] = useState({ currentPassword: "", password: "", confirmPassword: "" });
  const [message, setMessage] = useState("");

  useEffect(() => { api<MeData>("/api/auth/me").then(setData); }, []);

  async function changePassword(event: React.FormEvent) {
    event.preventDefault();
    try {
      await api("/api/profile/password", { method: "POST", body: JSON.stringify(form) });
      setMessage("密码修改成功，请重新登录");
      setTimeout(() => router.push("/login"), 1200);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "修改失败");
    }
  }

  async function logout() {
    await fetch("/api/auth/logout", { method: "POST" });
    router.push("/login");
  }

  const cards = [
    { label: "用户名", value: data?.user.username || "-", icon: UserRound },
    { label: "会员等级", value: data?.membership.planName || "-", icon: Shield },
    { label: "会员到期", value: data?.membership.expiresAt ? new Date(data.membership.expiresAt).toLocaleString() : "无到期时间", icon: CalendarClock },
    { label: "剩余次数", value: data?.membership.unlimited ? "无限" : String(data?.membership.remaining ?? 0), icon: KeyRound }
  ];

  return (
    <div className="space-y-6">
      <header><p className="text-xs font-semibold tracking-[.24em] text-amber-400">ACCOUNT</p><h1 className="mt-2 text-2xl font-bold text-white">用户中心</h1></header>
      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {cards.map(({ label, value, icon: Icon }) => <div key={label} className="glass-card rounded-2xl p-5"><Icon size={19} className="text-amber-400" /><p className="mt-4 text-xs text-slate-600">{label}</p><p className="mt-1 font-semibold text-white">{value}</p></div>)}
      </section>
      <section className="grid gap-5 lg:grid-cols-2">
        <div className="glass-card rounded-3xl p-6">
          <h2 className="flex items-center gap-2 font-bold text-white"><Laptop size={18} className="text-amber-400" />绑定设备</h2>
          {data?.device ? <div className="mt-5 space-y-3 text-sm"><div className="flex justify-between"><span className="text-slate-600">浏览器 / 系统</span><span>{data.device.browser || "-"} · {data.device.os || "-"}</span></div><div className="flex justify-between"><span className="text-slate-600">状态</span><span className="text-emerald-400">{data.device.boundAt ? "已绑定" : "待会员开通后绑定"}</span></div><div className="flex justify-between"><span className="text-slate-600">最后登录</span><span>{new Date(data.device.lastSeenAt).toLocaleString()}</span></div><p className="break-all rounded-xl bg-black/20 p-3 font-mono text-[10px] text-slate-600">DeviceID: {data.device.deviceId}</p></div> : <p className="mt-5 text-sm text-slate-600">暂无设备信息，请重新登录。</p>}
          <p className="mt-4 text-xs leading-5 text-slate-600">会员账号首次登录后绑定当前设备。如需更换设备，请联系客服或由管理员解绑。</p>
        </div>
        <form onSubmit={changePassword} className="glass-card rounded-3xl p-6">
          <h2 className="font-bold text-white">修改密码</h2>
          <div className="mt-5 space-y-3">
            <input required type="password" minLength={8} placeholder="当前密码" className="dark-input w-full rounded-xl px-4 py-3 text-sm" value={form.currentPassword} onChange={(e) => setForm({ ...form, currentPassword: e.target.value })} />
            <input required type="password" minLength={10} placeholder="新密码（至少 10 位）" className="dark-input w-full rounded-xl px-4 py-3 text-sm" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} />
            <input required type="password" minLength={10} placeholder="确认新密码" className="dark-input w-full rounded-xl px-4 py-3 text-sm" value={form.confirmPassword} onChange={(e) => setForm({ ...form, confirmPassword: e.target.value })} />
          </div>
          <button className="gold-button mt-4 w-full rounded-xl px-4 py-3 text-sm font-bold">保存新密码</button>
          {message && <p className="mt-3 text-sm text-amber-300">{message}</p>}
        </form>
      </section>
      <button onClick={logout} className="inline-flex items-center gap-2 rounded-xl border border-red-500/20 bg-red-500/5 px-4 py-3 text-sm text-red-300"><LogOut size={16} />退出登录</button>
    </div>
  );
}
