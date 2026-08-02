import { IpQueryPanel } from "@/components/ip-query-panel";

export default function IpQueryPage() {
  return (
    <div className="space-y-6">
      <header>
        <p className="text-xs font-semibold tracking-[.24em] text-amber-400">IP RISK CHECK</p>
        <h1 className="mt-2 text-2xl font-bold text-white">IP 查重</h1>
        <p className="mt-2 text-sm text-slate-500">逐条比较完整 IP 与 A/B/C/D 四段，查询完成后自动写入历史记录。</p>
      </header>
      <IpQueryPanel />
    </div>
  );
}
