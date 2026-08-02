import { SettingsView } from "@/components/settings-view";
import { OwnerOnly } from "@/components/owner-only";

export default function SettingsPage() {
  return (
    <OwnerOnly>
      <div className="space-y-5">
        <div>
          <p className="text-xs font-semibold tracking-[.24em] text-amber-400">SYSTEM SETTINGS</p>
          <h1 className="mt-2 text-2xl font-bold text-white">系统设置</h1>
          <p className="mt-2 text-sm text-slate-500">安全配置通过服务器环境变量管理，避免网页端泄露或误改。仅总管理员可查看。</p>
        </div>
        <SettingsView />
      </div>
    </OwnerOnly>
  );
}
