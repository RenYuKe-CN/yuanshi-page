import { CheckCircle2, ShieldCheck, Sparkles } from "lucide-react";

export function AuthBrandPanel() {
  const features = [
    "帮助用户统一管理交易所环境",
    "快速检测 IP 重复率",
    "安全管理历史记录"
  ];
  return (
    <section className="relative hidden overflow-hidden border-r border-white/5 p-10 lg:flex lg:flex-col lg:justify-between">
      <div className="absolute inset-0 bg-[url('/brand/crypto-background.jpg')] bg-cover bg-center opacity-20" />
      <div className="absolute inset-0 bg-gradient-to-br from-[#07101e]/95 via-[#07101e]/88 to-[#151006]/75" />
      <div className="relative">
        <div className="flex items-center gap-4">
          <img src="/brand/ck-logo.jpg" alt="CK原石图标" className="h-16 w-16 rounded-2xl border border-amber-400/60 object-cover shadow-[0_0_30px_rgba(245,158,11,.2)]" />
          <div><h1 className="text-2xl font-bold text-white">原石金手指</h1><p className="mt-1 text-xs font-semibold tracking-[.24em] text-amber-400">IP RISK INTELLIGENCE</p></div>
        </div>
        <div className="mt-20 max-w-xl">
          <span className="inline-flex items-center gap-2 rounded-full border border-amber-400/20 bg-amber-400/5 px-3 py-1 text-xs text-amber-300"><Sparkles size={13} />商业级 SaaS 管理平台</span>
          <h2 className="mt-6 text-4xl font-bold leading-tight text-white">让每一次网络环境配置<br /><span className="text-amber-300">更清晰、更安全。</span></h2>
          <p className="mt-5 max-w-lg text-sm leading-7 text-slate-400">面向 CEX 与 DEX 业务场景的 IP 查重、会员授权、设备管理与历史审计平台。</p>
          <div className="mt-8 space-y-4">
            {features.map((feature) => <div key={feature} className="flex items-center gap-3 text-sm text-slate-300"><CheckCircle2 size={18} className="text-amber-400" />{feature}</div>)}
          </div>
        </div>
      </div>
      <div className="relative flex items-center gap-3 text-xs text-slate-500"><ShieldCheck size={16} className="text-emerald-400" />密码加密 · 权限隔离 · 操作审计 · 链上自动验单</div>
    </section>
  );
}
