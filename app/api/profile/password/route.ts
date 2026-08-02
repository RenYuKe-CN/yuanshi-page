import bcrypt from "bcryptjs";
import { NextRequest } from "next/server";
import { requireUser } from "@/lib/auth";
import { prisma } from "@/lib/db";
import { changePasswordSchema } from "@/lib/validators";
import { assertTrustedOrigin, getClientIp, jsonError } from "@/lib/security";

export async function POST(request: NextRequest) {
  try {
    assertTrustedOrigin(request);
    const user = await requireUser(request);
    const body = changePasswordSchema.parse(await request.json());
    const existing = await prisma.user.findUniqueOrThrow({ where: { id: user.id } });
    if (!(await bcrypt.compare(body.currentPassword, existing.passwordHash))) {
      return jsonError("当前密码错误", 400);
    }
    const passwordHash = await bcrypt.hash(body.password, 12);
    await prisma.$transaction([
      prisma.user.update({
        where: { id: user.id },
        data: { passwordHash, sessionVersion: { increment: 1 } }
      }),
      prisma.operationLog.create({
        data: {
          userId: user.id,
          action: "CHANGE_PASSWORD",
          targetType: "USER",
          targetId: user.id,
          ipAddress: getClientIp(request)
        }
      })
    ]);
    return Response.json({ ok: true, relogin: true });
  } catch (error) {
    return jsonError(error instanceof Error ? error.message : "修改密码失败", 400);
  }
}
