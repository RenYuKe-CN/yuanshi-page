import { NextRequest } from "next/server";
import { requireOwner } from "@/lib/auth";
import { prisma } from "@/lib/db";
import { planUpdateSchema } from "@/lib/validators";
import { assertTrustedOrigin, jsonError } from "@/lib/security";

export async function PATCH(request: NextRequest, context: { params: Promise<{ id: string }> }) {
  try {
    assertTrustedOrigin(request);
    const admin = await requireOwner(request);
    const { id } = await context.params;
    const body = planUpdateSchema.parse(await request.json());
    const plan = await prisma.membershipPlan.update({ where: { id }, data: body });
    await prisma.operationLog.create({
      data: { userId: admin.id, action: "UPDATE_MEMBERSHIP_PLAN", targetType: "MEMBERSHIP_PLAN", targetId: id, detail: body }
    });
    return Response.json({ plan: { ...plan, priceUsd: plan.priceUsd.toString() } });
  } catch (error) {
    return jsonError(error instanceof Error ? error.message : "更新套餐失败", 400);
  }
}
