import { z } from "zod";
import { NextRequest } from "next/server";
import { requireOwner } from "@/lib/auth";
import { prisma } from "@/lib/db";
import { assertTrustedOrigin, jsonError } from "@/lib/security";

const schema = z.object({
  active: z.boolean().optional(),
  name: z.string().trim().min(2).max(100).optional(),
  category: z.enum(["CEX", "DEX", "OTHER"]).optional(),
  iconUrl: z.string().trim().max(500).nullable().optional()
});

export async function PATCH(request: NextRequest, context: { params: Promise<{ id: string }> }) {
  try {
    assertTrustedOrigin(request);
    const admin = await requireOwner(request);
    const { id } = await context.params;
    const body = schema.parse(await request.json());
    const exchange = await prisma.exchange.update({ where: { id }, data: body });
    await prisma.operationLog.create({
      data: { userId: admin.id, action: "UPDATE_EXCHANGE", targetType: "EXCHANGE", targetId: id, detail: body }
    });
    return Response.json({ exchange });
  } catch (error) {
    return jsonError(error instanceof Error ? error.message : "更新交易所失败", 400);
  }
}
