import { Mail, MessageCircle, Send } from "lucide-react";

export default function ContactPage() {
  const contacts = [
    { title: "Telegram 客服", value: "@mommo10338", href: "https://t.me/mommo10338", icon: Send, note: "账号、会员、设备解绑与售后支持" },
    { title: "技术业务交流群", value: "t.me/B132609", href: "https://t.me/B132609", icon: MessageCircle, note: "产品更新、技术交流与业务合作" },
    { title: "邮箱", value: "请联系管理员配置", href: "", icon: Mail, note: "云服务器部署后可在系统设置中配置" }
  ];
  return (
    <div className="space-y-6">
      <header><p className="text-xs font-semibold tracking-[.24em] text-amber-400">SUPPORT</p><h1 className="mt-2 text-2xl font-bold text-white">联系客服</h1><p className="mt-2 text-sm text-slate-500">需要设备解绑、会员帮助或业务合作时，请通过以下官方渠道联系。</p></header>
      <section className="grid gap-5 md:grid-cols-3">
        {contacts.map(({ title, value, href, icon: Icon, note }) => (
          <article key={title} className="glass-card rounded-3xl p-6">
            <span className="grid h-11 w-11 place-items-center rounded-2xl border border-amber-400/20 bg-amber-400/10 text-amber-400"><Icon size={20} /></span>
            <h2 className="mt-5 font-bold text-white">{title}</h2>
            <p className="mt-2 text-sm text-amber-300">{value}</p>
            <p className="mt-3 text-xs leading-5 text-slate-600">{note}</p>
            {href && <a href={href} target="_blank" rel="noopener noreferrer" className="gold-button mt-6 inline-flex rounded-xl px-4 py-2 text-sm font-bold">立即联系</a>}
          </article>
        ))}
      </section>
    </div>
  );
}
