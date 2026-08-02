import { HistoryTable } from "@/components/history-table";

export default function HistoryPage() {
  return (
    <div className="space-y-5">
      <div>
        <p className="text-xs font-semibold tracking-[.24em] text-amber-400">QUERY HISTORY</p>
        <h1 className="mt-2 text-2xl font-bold text-white">查询历史</h1>
        <p className="mt-2 text-sm text-slate-500">支持 IP、分段、交易所、用户和日期范围筛选，可导出 CSV 或 Excel。</p>
      </div>
      <HistoryTable />
    </div>
  );
}
