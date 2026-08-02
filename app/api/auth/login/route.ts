import bcrypt from "bcryptjs";
import { NextRequest } from "next/server";
import { prisma } from "@/lib/db";
import { loginSchema } from "@/lib/validators";
import { checkRateLimit } from "@/lib/rate-limit";
import { getClientIp, assertTrustedOrigin, jsonError } from "@/lib/security";
import { setSessionCookie } from "@/lib/auth";
import { writeOperationLog } from "@/lib/log";
import { enforceMembershipDevice, recordLoginDevice } from "@/lib/device";
import { getMembership } from "@/lib/membership";

export async function POST(request: NextRequest) {
  try {
    assertTrustedOrigin(request);
    const clientIp = getClientIp(request);
    const limit = Number(process.env.LOGIN_RATE_LIMIT || 5);
    const rate = checkRateLimit(`login:${clientIp}`, limit, 60_000);
    if (!rate.ok) return jsonError("登录过于频繁，请稍后再试", 429);

    const body = loginSchema.parse(await request.json());
    const identifier = body.username.toLowerCase();
    const user = await prisma.user.findFirst({
      where: identifier.includes("@")
        ? { OR: [{ username: body.username }, { email: identifier }] }
        : { username: body.username }
    });
    if (!user || user.status !== "ACTIVE" || user.deletedAt) return jsonError("用户名或密码错误", 401);

    const ok = await bcrypt.compare(body.password, user.passwordHash);
    if (!ok) return jsonError("用户名或密码错误", 401);

    const device = await recordLoginDevice(user.id, body.device, clientIp);
    const membership = user.role === "ADMIN" ? null : await getMembership(user.id);
    if (membership?.status === "ACTIVE" && membership.plan.code !== "FREE") {
      await enforceMembershipDevice(user.id, device.deviceId);
    }

    await prisma.user.update({
      where: { id: user.id },
      data: { lastLoginAt: new Date() }
    });

    await setSessionCookie({
      id: user.id,
      username: user.username,
      role: user.role,
      isOwner: user.isOwner,
      sessionVersion: user.sessionVersion,
      deviceId: device.deviceId
    });
    await writeOperationLog({
      userId: user.id,
      action: "LOGIN",
      targetType: "USER",
      targetId: user.id,
      ipAddress: clientIp
    });

    return Response.json({
      user: { id: user.id, username: user.username, role: user.role, isOwner: user.isOwner },
      deviceId: device.deviceId
    });
  } catch (error) {
    return jsonError(error instanceof Error ? error.message : "登录失败", 400);
  }
}
