import Link from "next/link";

export default function StatementPage() {
  return (
    <main className="min-h-screen bg-slate-950 px-4 py-12 text-slate-200">
      <article className="mx-auto max-w-3xl rounded-3xl border border-amber-400/20 bg-slate-900/80 p-6 shadow-2xl backdrop-blur md:p-10">
        <p className="text-xs font-semibold tracking-[.28em] text-amber-400">REGISTRATION STATEMENT</p>
        <h1 className="mt-3 text-2xl font-bold text-white">原石金手指 · IP查重管理系统 用户注册声明</h1>
        <ol className="mt-8 list-decimal space-y-4 pl-6 text-sm leading-7 text-slate-300">
          <li>本系统主要用于 IP 管理、IP 查重及环境管理。</li>
          <li>系统仅保存业务所需数据；会员、订单、设备授权等信息将安全存储于服务器，用于账号、会员及授权管理，不会无故向第三方披露。</li>
          <li>本系统仅用于帮助用户管理自身网络环境，避免环境冲突。</li>
          <li>用户必须遵守中华人民共和国法律法规及各交易平台、交易所相关规则。</li>
          <li>禁止用于非法多账号、欺诈、洗钱、市场操纵及任何违法违规用途。</li>
          <li>用户自行承担因自身使用行为产生的一切法律责任。</li>
          <li>如发现共享账号、破解程序、恶意攻击或非法使用，开发者有权暂停、封禁或终止服务。</li>
          <li>注册即代表已阅读、已理解并同意本声明。</li>
        </ol>
        <Link href="/register" className="mt-8 inline-flex rounded-xl bg-amber-400 px-5 py-3 font-semibold text-slate-950">返回注册</Link>
      </article>
    </main>
  );
}
