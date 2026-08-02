import bcrypt from "bcryptjs";
import crypto from "node:crypto";
import { NextRequest } from "next/server";
import { prisma } from "@/lib/db";
import { registerSchema } from "@/lib/validators";
import { checkRateLimit } from "@/lib/rate-limit";
import { assertTrustedOrigin, getClientIp, jsonError } from "@/lib/security";
import { writeOperationLog } from "@/lib/log";

export async function POST(request: NextRequest) {
  try {
    assertTrustedOrigin(request);
    const clientIp = getClientIp(request);
    const rate = checkRateLimit(`register:${clientIp}`, 5, 60 * 60_000);
    if (!rate.ok) return jsonError("注册过于频繁，请一小时后再试", 429);

    const body = registerSchema.parse(await request.json());
    const recoveryCode = crypto.randomBytes(18).toString("base64url");
    const [passwordHash, recoveryHash] = await Promise.all([
      bcrypt.hash(body.password, 12),
      bcrypt.hash(recoveryCode, 12)
    ]);
    const freePlan = await prisma.membershipPlan.findUnique({ where: { code: "FREE" } });
    if (!freePlan) throw new Error("会员套餐尚未初始化，请联系管理员");
    const user = await prisma.user.create({
      data: {
        username: body.username,
        email: body.email,
        passwordHash,
        recoveryHash,
        role: "USER",
        isOwner: false,
        status: "ACTIVE",
        membership: {
          create: {
            planId: freePlan.id,
            status: "FREE",
            queryLimit: 0,
            queryUsed: 0
          }
        }
      },
      select: { id: true, username: true, email: true }
    });
    await writeOperationLog({
      userId: user.id,
      action: "REGISTER_USER",
      targetType: "USER",
      targetId: user.id,
      detail: { username: user.username },
      ipAddress: clientIp
    });
    return Response.json({ user, recoveryCode }, { status: 201 });
  } catch (error) {
    const message = error instanceof Error ? error.message : "注册失败";
    if (message.includes("Unique constraint")) return jsonError("用户名或邮箱已被使用", 409);
    return jsonError(message, 400);
  }
}
