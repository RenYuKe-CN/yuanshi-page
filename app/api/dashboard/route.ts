import { NextRequest } from "next/server";
import { requireUser } from "@/lib/auth";
import { prisma } from "@/lib/db";
import { getMembership, serializeMembership } from "@/lib/membership";
import { jsonError } from "@/lib/security";

export async function GET(request: NextRequest) {
  try {
    const user = await requireUser(request);
    const start = new Date();
    start.setHours(0, 0, 0, 0);
    const monthStart = new Date(start.getFullYear(), start.getMonth(), 1);
    const where = user.isOwner ? {} : { userId: user.id };
    const [today, total, recent, membership] = await Promise.all([
      prisma.operationLog.count({ where: { userId: user.id, action: "IP_QUERY", createdAt: { gte: start } } }),
      prisma.operationLog.count({ where: { ...where, action: "IP_QUERY" } }),
      prisma.ipRecord.findMany({
        where,
        include: { user: { select: { username: true } } },
        orderBy: { lastSeenAt: "desc" },
        take: 6
      }),
      user.role === "ADMIN" ? null : getMembership(user.id)
    ]);
    const month = await prisma.operationLog.count({
      where: { userId: user.id, action: "IP_QUERY", createdAt: { gte: monthStart } }
    });
    return Response.json({
      stats: {
        member: serializeMembership(membership, user.role === "ADMIN"),
        today,
        month,
        total
      },
      recent
    });
  } catch (error) {
    return jsonError(error instanceof Error ? error.message : "读取首页失败", 401);
  }
}
