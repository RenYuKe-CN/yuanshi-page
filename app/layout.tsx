import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "原石金手指 · IP 查重管理系统",
  description: "登录后可用的 IP 查重、历史管理与审计系统",
  icons: { icon: "/brand/ck-logo.jpg" }
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}
