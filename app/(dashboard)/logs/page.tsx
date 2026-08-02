import { LogsTable } from "@/components/logs-table";
import { OwnerOnly } from "@/components/owner-only";

export default function LogsPage() {
  return (
    <OwnerOnly>
      <div className="space-y-5">
        <div>
          <p className="text-xs font-semibold tracking-[.24em] text-amber-400">AUDIT LOG</p>
          <h1 className="mt-2 text-2xl font-bold text-white">操作日志</h1>
          <p className="mt-1 text-sm text-slate-500">记录登录、查询、删除和用户管理操作，仅总管理员可查看。</p>
        </div>
        <LogsTable />
      </div>
    </OwnerOnly>
  );
}
