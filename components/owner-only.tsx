"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

type MeResponse = {
  user: {
    username: string;
    role: "ADMIN" | "USER";
    isOwner: boolean;
  } | null;
};

export function OwnerOnly({ children }: { children: React.ReactNode }) {
  const [allowed, setAllowed] = useState<boolean | null>(null);

  useEffect(() => {
    fetch("/api/auth/me", { cache: "no-store" })
      .then((response) => response.json())
      .then((data: MeResponse) => setAllowed(Boolean(data.user?.isOwner)))
      .catch(() => setAllowed(false));
  }, []);

  if (allowed === null) {
    return (
      <div className="glass-card rounded-3xl p-8 text-sm text-slate-500">
        正在校验总管理员权限...
      </div>
    );
  }

  if (!allowed) {
    return (
      <div className="glass-card rounded-3xl p-8">
        <p className="text-xs font-semibold tracking-[.24em] text-amber-400">OWNER ONLY</p>
        <h1 className="mt-3 text-2xl font-bold text-white">需要总管理员权限</h1>
        <p className="mt-3 text-sm text-slate-500">
          当前页面包含会员数据、系统设置或后台管理信息，仅总管理员可以查看。
        </p>
        <Link href="/" className="gold-button mt-6 inline-flex rounded-xl px-5 py-3 text-sm font-bold">
          返回 IP 查重
        </Link>
      </div>
    );
  }

  return <>{children}</>;
}
