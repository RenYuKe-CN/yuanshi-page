import bcrypt from "bcryptjs";
import crypto from "node:crypto";
import { NextRequest } from "next/server";
import { prisma } from "@/lib/db";
import { requireOwner } from "@/lib/auth";
import { userCreateSchema } from "@/lib/validators";
import { assertTrustedOrigin, getClientIp, jsonError } from "@/lib/security";
import { writeOperationLog } from "@/lib/log";

export async function GET(request: NextRequest) {
  try {
    const admin = await requireOwner(request);
    const users = await prisma.user.findMany({
      where: { deletedAt: null },
      select: {
        id: true,
        username: true,
        role: true,
        isOwner: true,
        status: true,
        lastLoginAt: true,
        createdAt: true,
        updatedAt: true
      },
      orderBy: { createdAt: "desc" }
    });
    return Response.json({ users, viewer: { id: admin.id, isOwner: admin.isOwner } });
  } catch (error) {
    const message = error instanceof Error ? error.message : "读取用户失败";
    return jsonError(message, message.includes("管理员") ? 403 : 401);
  }
}

export async function POST(request: NextRequest) {
  try {
    assertTrustedOrigin(request);
    const admin = await requireOwner(request);
    const body = userCreateSchema.parse(await request.json());
    if (body.role === "ADMIN" && !admin.isOwner) return jsonError("只有总管理员可以添加备用管理员", 403);
    const recoveryCode = crypto.randomBytes(18).toString("base64url");
    const [passwordHash, recoveryHash] = await Promise.all([
      bcrypt.hash(body.password, 12),
      bcrypt.hash(recoveryCode, 12)
    ]);
    const freePlan = await prisma.membershipPlan.findUnique({ where: { code: "FREE" } });
    if (!freePlan) throw new Error("会员套餐尚未初始化");
    const user = await prisma.user.create({
      data: {
        username: body.username,
        email: body.email,
        passwordHash,
        recoveryHash,
        role: body.role,
        isOwner: false,
        status: body.status,
        membership: { create: { planId: freePlan.id, status: "FREE", queryLimit: 0 } }
      },
      select: { id: true, username: true, role: true, status: true, createdAt: true }
    });
    await writeOperationLog({
      userId: admin.id,
      action: "CREATE_USER",
      targetType: "USER",
      targetId: user.id,
      detail: { username: user.username, role: user.role, status: user.status },
      ipAddress: getClientIp(request)
    });
    return Response.json({ user, recoveryCode });
  } catch (error) {
    const message = error instanceof Error ? error.message : "创建用户失败";
    return jsonError(message, message.includes("管理员") ? 403 : 400);
  }
}
