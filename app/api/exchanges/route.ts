import { NextRequest } from "next/server";
import { requireUser } from "@/lib/auth";
import { prisma } from "@/lib/db";
import { jsonError } from "@/lib/security";

export async function GET(request: NextRequest) {
  try {
    await requireUser(request);
    const exchanges = await prisma.exchange.findMany({
      where: { active: true },
      select: { name: true, category: true, iconUrl: true },
      orderBy: [{ category: "asc" }, { sortOrder: "asc" }]
    });
    return Response.json({ exchanges });
  } catch (error) {
    return jsonError(error instanceof Error ? error.message : "读取交易所失败", 401);
  }
}
