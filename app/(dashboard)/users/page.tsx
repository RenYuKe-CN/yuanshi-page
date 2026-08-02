import { UsersAdmin } from "@/components/users-admin";
import { OwnerOnly } from "@/components/owner-only";

export default function UsersPage() {
  return (
    <OwnerOnly>
      <div className="space-y-5">
        <div>
          <p className="text-xs font-semibold tracking-[.24em] text-amber-400">USER MANAGEMENT</p>
          <h1 className="mt-2 text-2xl font-bold text-white">用户管理</h1>
          <p className="mt-1 text-sm text-slate-500">仅总管理员可新增用户、调整角色和启停状态。</p>
        </div>
        <UsersAdmin />
      </div>
    </OwnerOnly>
  );
}
