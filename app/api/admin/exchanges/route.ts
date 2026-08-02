import { z } from "zod";
import { NextRequest } from "next/server";
import { requireOwner } from "@/lib/auth";
import { prisma } from "@/lib/db";
import { assertTrustedOrigin, jsonError } from "@/lib/security";

const schema = z.object({
  name: z.string().trim().min(2).max(100),
  category: z.enum(["CEX", "DEX", "OTHER"]),
  iconUrl: z.string().trim().max(500).nullable().optional()
});

export async function POST(request: NextRequest) {
  try {
    assertTrustedOrigin(request);
    const admin = await requireOwner(request);
    const body = schema.parse(await request.json());
    const slug = `${body.name.toLowerCase().replace(/[^a-z0-9]+/g, "-")}-${Date.now()}`;
    const exchange = await prisma.exchange.create({ data: { ...body, slug } });
    await prisma.operationLog.create({
      data: { userId: admin.id, action: "CREATE_EXCHANGE", targetType: "EXCHANGE", targetId: exchange.id, detail: body }
    });
    return Response.json({ exchange }, { status: 201 });
  } catch (error) {
    return jsonError(error instanceof Error ? error.message : "新增交易所失败", 400);
  }
}
