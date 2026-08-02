import { z } from "zod";
import { NextRequest } from "next/server";
import { requireOwner } from "@/lib/auth";
import { prisma } from "@/lib/db";
import { assertTrustedOrigin, jsonError } from "@/lib/security";
import { membershipReminderAt } from "@/lib/membership";

const schema = z.object({
  planCode: z.enum(["FREE", "STARSHIP", "PRO"]),
  status: z.enum(["FREE", "ACTIVE", "EXPIRED", "SUSPENDED"]),
  queryLimit: z.number().int().min(0).max(1_000_000).nullable(),
  queryUsed: z.number().int().min(0).max(1_000_000).default(0),
  expiresAt: z.string().datetime().nullable()
});

export async function PATCH(request: NextRequest, context: { params: Promise<{ userId: string }> }) {
  try {
    assertTrustedOrigin(request);
    const admin = await requireOwner(request);
    const { userId } = await context.params;
    const target = await prisma.user.findUniqueOrThrow({ where: { id: userId } });
    if (target.isOwner && target.id !== admin.id) return jsonError("总管理员会员不可由备用管理员修改", 403);
    const body = schema.parse(await request.json());
    const plan = await prisma.membershipPlan.findUniqueOrThrow({ where: { code: body.planCode } });
    const expiresAt = body.expiresAt ? new Date(body.expiresAt) : null;
    const membership = await prisma.membership.upsert({
      where: { userId },
      create: {
        userId, planId: plan.id, status: body.status, queryLimit: body.queryLimit,
        queryUsed: body.queryUsed, startsAt: body.status === "ACTIVE" ? new Date() : null,
        expiresAt, reminderAt: expiresAt ? membershipReminderAt(expiresAt) : null
      },
      update: {
        planId: plan.id, status: body.status, queryLimit: body.queryLimit,
        queryUsed: body.queryUsed, expiresAt,
        reminderAt: expiresAt ? membershipReminderAt(expiresAt) : null
      },
      include: { plan: true }
    });
    await prisma.operationLog.create({
      data: { userId: admin.id, action: "UPDATE_MEMBERSHIP", targetType: "USER", targetId: userId, detail: body }
    });
    return Response.json({ membership });
  } catch (error) {
    return jsonError(error instanceof Error ? error.message : "更新会员失败", 400);
  }
}
