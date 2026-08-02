import bcrypt from "bcryptjs";
import crypto from "node:crypto";
import { NextRequest } from "next/server";
import { prisma } from "@/lib/db";
import { recoverPasswordSchema } from "@/lib/validators";
import { checkRateLimit } from "@/lib/rate-limit";
import { assertTrustedOrigin, getClientIp, jsonError } from "@/lib/security";
import { writeOperationLog } from "@/lib/log";

export async function POST(request: NextRequest) {
  try {
    assertTrustedOrigin(request);
    const clientIp = getClientIp(request);
    const rate = checkRateLimit(`recover:${clientIp}`, 5, 15 * 60_000);
    if (!rate.ok) return jsonError("尝试次数过多，请 15 分钟后再试", 429);

    const body = recoverPasswordSchema.parse(await request.json());
    const user = await prisma.user.findUnique({ where: { username: body.username } });
    if (!user || user.status !== "ACTIVE" || user.deletedAt || !user.recoveryHash) {
      return jsonError("用户名或恢复码错误", 401);
    }
    if (!(await bcrypt.compare(body.recoveryCode, user.recoveryHash))) {
      return jsonError("用户名或恢复码错误", 401);
    }

    const recoveryCode = crypto.randomBytes(18).toString("base64url");
    const [passwordHash, recoveryHash] = await Promise.all([
      bcrypt.hash(body.password, 12),
      bcrypt.hash(recoveryCode, 12)
    ]);
    await prisma.user.update({
      where: { id: user.id },
      data: { passwordHash, recoveryHash, sessionVersion: { increment: 1 } }
    });
    await writeOperationLog({
      userId: user.id,
      action: "RECOVER_PASSWORD",
      targetType: "USER",
      targetId: user.id,
      detail: { sessionInvalidated: true },
      ipAddress: clientIp
    });
    return Response.json({ recoveryCode });
  } catch (error) {
    return jsonError(error instanceof Error ? error.message : "密码重置失败", 400);
  }
}
