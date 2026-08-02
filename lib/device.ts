import crypto from "node:crypto";
import type { Prisma } from "@prisma/client";
import { prisma } from "@/lib/db";

export type DeviceInput = {
  fingerprint: string;
  browser?: string;
  os?: string;
  userAgent?: string;
};

function hmac(value: string) {
  const secret = process.env.AUTH_SECRET;
  if (!secret || secret.length < 32) throw new Error("AUTH_SECRET 必须至少 32 个字符");
  return crypto.createHmac("sha256", secret).update(value).digest("hex");
}

export function deriveDeviceIdentity(userId: string, input: DeviceInput) {
  if (!input.fingerprint || input.fingerprint.length < 16 || input.fingerprint.length > 2048) {
    throw new Error("无法识别当前设备，请启用浏览器 JavaScript 后重试");
  }
  const fingerprintHash = hmac(`fingerprint:${input.fingerprint}`);
  const deviceId = hmac(`device:${userId}:${fingerprintHash}`);
  return { fingerprintHash, deviceId };
}

export async function recordLoginDevice(
  userId: string,
  input: DeviceInput,
  ipAddress: string
) {
  const identity = deriveDeviceIdentity(userId, input);
  const device = await prisma.device.upsert({
    where: {
      userId_fingerprintHash: {
        userId,
        fingerprintHash: identity.fingerprintHash
      }
    },
    create: {
      userId,
      ...identity,
      browser: input.browser?.slice(0, 100),
      os: input.os?.slice(0, 100),
      userAgent: input.userAgent?.slice(0, 500),
      ipAddress
    },
    update: {
      browser: input.browser?.slice(0, 100),
      os: input.os?.slice(0, 100),
      userAgent: input.userAgent?.slice(0, 500),
      ipAddress,
      lastSeenAt: new Date()
    }
  });
  if (device.status === "BLOCKED") throw new Error("当前设备已被封禁，请联系客服");
  return device;
}

export async function enforceMembershipDevice(userId: string, deviceId?: string | null) {
  if (!deviceId) throw new Error("当前登录缺少设备授权，请退出后重新登录");
  const bound = await prisma.device.findFirst({
    where: { userId, boundAt: { not: null }, status: "ACTIVE" },
    orderBy: { boundAt: "asc" }
  });
  if (!bound) {
    const current = await prisma.device.findUnique({ where: { deviceId } });
    if (!current || current.userId !== userId || current.status !== "ACTIVE") {
      throw new Error("无法绑定当前设备，请联系客服");
    }
    await prisma.device.update({
      where: { id: current.id },
      data: { boundAt: new Date() }
    });
    return current;
  }
  if (bound.deviceId !== deviceId) {
    throw new Error("账号已绑定其它设备，请联系客服");
  }
  return bound;
}

export async function bindDeviceAfterActivation(
  tx: Prisma.TransactionClient,
  userId: string,
  deviceId?: string | null
) {
  if (!deviceId) return;
  const alreadyBound = await tx.device.findFirst({
    where: { userId, boundAt: { not: null }, status: "ACTIVE" }
  });
  if (alreadyBound) return;
  const current = await tx.device.findFirst({
    where: { userId, deviceId, status: "ACTIVE" }
  });
  if (current) {
    await tx.device.update({ where: { id: current.id }, data: { boundAt: new Date() } });
  }
}
