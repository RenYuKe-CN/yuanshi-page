import bcrypt from "bcryptjs";
import { NextRequest } from "next/server";
import { prisma } from "@/lib/db";
import { requireOwner } from "@/lib/auth";
import { userUpdateSchema } from "@/lib/validators";
import { assertTrustedOrigin, getClientIp, jsonError } from "@/lib/security";
import { writeOperationLog } from "@/lib/log";

export async function PATCH(request: NextRequest, context: { params: Promise<{ id: string }> }) {
  try {
    assertTrustedOrigin(request);
    const admin = await requireOwner(request);
    const { id } = await context.params;
    const body = userUpdateSchema.parse(await request.json());
    const target = await prisma.user.findUnique({ where: { id } });
    if (!target || target.deletedAt) return jsonError("用户不存在", 404);
    if (target.isOwner || id === admin.id) return jsonError("该账号受保护，不能修改", 403);
    if (!admin.isOwner && target.role === "ADMIN") return jsonError("备用管理员不能管理其他管理员", 403);
    if (!admin.isOwner && body.role === "ADMIN") return jsonError("只有总管理员可以授予管理员权限", 403);
    const data = {
      role: body.role,
      status: body.status,
      passwordHash: body.password ? await bcrypt.hash(body.password, 12) : undefined,
      sessionVersion: body.password || body.status === "DISABLED" ? { increment: 1 } : undefined
    };
    const user = await prisma.user.update({
      where: { id },
      data,
      select: { id: true, username: true, role: true, status: true, updatedAt: true }
    });
    await writeOperationLog({
      userId: admin.id,
      action: "UPDATE_USER",
      targetType: "USER",
      targetId: id,
      detail: { role: body.role, status: body.status, passwordChanged: Boolean(body.password) },
      ipAddress: getClientIp(request)
    });
    return Response.json({ user });
  } catch (error) {
    const message = error instanceof Error ? error.message : "更新用户失败";
    return jsonError(message, message.includes("管理员") ? 403 : 400);
  }
}

export async function DELETE(request: NextRequest, context: { params: Promise<{ id: string }> }) {
  try {
    assertTrustedOrigin(request);
    const admin = await requireOwner(request);
    const { id } = await context.params;
    const target = await prisma.user.findUnique({ where: { id } });
    if (!target || target.deletedAt) return jsonError("用户不存在", 404);
    if (target.isOwner || id === admin.id) return jsonError("该账号受保护，不能删除", 403);
    if (!admin.isOwner && target.role !== "USER") return jsonError("备用管理员只能删除普通用户", 403);
    await prisma.user.update({
      where: { id },
      data: { status: "DISABLED", deletedAt: new Date(), sessionVersion: { increment: 1 } }
    });
    await writeOperationLog({
      userId: admin.id,
      action: "DELETE_USER",
      targetType: "USER",
      targetId: id,
      detail: { username: target.username, role: target.role, softDelete: true },
      ipAddress: getClientIp(request)
    });
    return Response.json({ ok: true });
  } catch (error) {
    const message = error instanceof Error ? error.message : "删除用户失败";
    return jsonError(message, message.includes("管理员") || message.includes("保护") ? 403 : 400);
  }
}
