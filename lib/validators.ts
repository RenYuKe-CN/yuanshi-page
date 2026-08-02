import { z } from "zod";
import { isAllowedEmailDomain } from "@/lib/email-domains";

export const loginSchema = z.object({
  username: z.string().trim().min(2).max(254),
  password: z.string().min(8).max(128),
  device: z.object({
    fingerprint: z.string().min(16).max(2048),
    browser: z.string().max(100).optional(),
    os: z.string().max(100).optional(),
    userAgent: z.string().max(500).optional()
  })
});

const username = z.string().trim().min(3).max(40).regex(/^[A-Za-z0-9_.\-\u4E00-\u9FFF]+$/u, "用户名仅支持中文、英文、数字及 . _ -");
const password = z.string().min(10).max(128);
const email = z.string().trim().email("请输入有效邮箱").max(254).transform((value) => value.toLowerCase()).refine(
  (value) => isAllowedEmailDomain(value),
  "请使用主流邮箱注册，例如 Gmail、QQ邮箱、Outlook、163、iCloud、Yahoo、Proton、阿里云邮箱或 Zoho Mail"
);

export const registerSchema = z.object({
  username,
  email,
  password,
  confirmPassword: password,
  acceptedStatement: z.literal(true, { message: "请先阅读并同意用户注册声明" })
}).refine((data) => data.password === data.confirmPassword, {
  message: "两次输入的密码不一致",
  path: ["confirmPassword"]
});

export const recoverPasswordSchema = z.object({
  username,
  recoveryCode: z.string().min(16).max(128),
  password,
  confirmPassword: password
}).refine((data) => data.password === data.confirmPassword, {
  message: "两次输入的新密码不一致",
  path: ["confirmPassword"]
});

export const ipQuerySchema = z.object({
  ip: z.string().trim().min(1, "请输入 IP 地址").max(15),
  exchange: z.string().trim().min(1, "请选择交易所").max(100)
});

export const userCreateSchema = z.object({
  username,
  email: email.optional(),
  password,
  role: z.enum(["ADMIN", "USER"]).default("USER"),
  status: z.enum(["ACTIVE", "DISABLED"]).default("ACTIVE")
});

export const userUpdateSchema = z.object({
  role: z.enum(["ADMIN", "USER"]).optional(),
  status: z.enum(["ACTIVE", "DISABLED"]).optional(),
  password: password.optional()
});

export const orderCreateSchema = z.object({
  planCode: z.enum(["STARSHIP", "PRO"]),
  paymentToken: z.enum(["USDT", "USDC"]),
  payerAddress: z.string().regex(/^0x[a-fA-F0-9]{40}$/).optional()
});

export const orderVerifySchema = z.object({
  orderId: z.string().cuid(),
  txHash: z.string().regex(/^0x[a-fA-F0-9]{64}$/, "Transaction Hash 格式错误")
});

export const announcementSchema = z.object({
  title: z.string().trim().min(2).max(120),
  content: z.string().trim().min(2).max(5000),
  type: z.enum(["NOTICE", "MAINTENANCE", "UPDATE", "ACTIVITY"]).default("NOTICE"),
  active: z.boolean().default(true),
  popup: z.boolean().default(false),
  expiresAt: z.string().datetime().nullable().optional()
});

export const planUpdateSchema = z.object({
  priceUsd: z.coerce.number().min(0).max(100000).optional(),
  durationDays: z.coerce.number().int().min(1).max(3650).optional(),
  queryLimit: z.coerce.number().int().min(0).max(1_000_000).nullable().optional(),
  active: z.boolean().optional()
});

export const changePasswordSchema = z.object({
  currentPassword: z.string().min(8).max(128),
  password,
  confirmPassword: password
}).refine((data) => data.password === data.confirmPassword, {
  message: "两次输入的新密码不一致",
  path: ["confirmPassword"]
});
