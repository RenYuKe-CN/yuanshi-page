import { NextRequest } from "next/server";
import { Prisma } from "@prisma/client";
import { prisma } from "@/lib/db";
import { requireUser } from "@/lib/auth";
import { jsonError } from "@/lib/security";

function intParam(value: string | null) {
  if (!value) return undefined;
  const num = Number(value);
  return Number.isInteger(num) ? num : undefined;
}

function buildWhere(searchParams: URLSearchParams): Prisma.IpRecordWhereInput {
  const where: Prisma.IpRecordWhereInput = {};
  const fullIp = searchParams.get("fullIp")?.trim();
  const exchange = searchParams.get("exchange")?.trim();
  const userId = searchParams.get("userId")?.trim();
  const from = searchParams.get("from")?.trim();
  const to = searchParams.get("to")?.trim();
  const similarity = intParam(searchParams.get("similarity"));

  if (fullIp) where.fullIp = { contains: fullIp };
  if (exchange) where.exchange = exchange;
  if (userId) where.userId = userId;
  if (similarity !== undefined) where.lastSimilarity = similarity;
  for (const key of ["segmentA", "segmentB", "segmentC", "segmentD"] as const) {
    const value = intParam(searchParams.get(key));
    if (value !== undefined) where[key] = value;
  }
  if (from || to) {
    where.createdAt = {
      gte: from ? new Date(from) : undefined,
      lte: to ? new Date(to) : undefined
    };
  }
  return where;
}

export async function GET(request: NextRequest) {
  try {
    const user = await requireUser(request);
    const params = request.nextUrl.searchParams;
    const page = Math.max(1, intParam(params.get("page")) || 1);
    const pageSize = Math.min(100, Math.max(10, intParam(params.get("pageSize")) || 20));
    const where = buildWhere(params);
    if (!user.isOwner) where.userId = user.id;

    const [items, total] = await Promise.all([
      prisma.ipRecord.findMany({
        where,
        include: { user: { select: { id: true, username: true } } },
        orderBy: [{ lastSeenAt: "desc" }],
        skip: (page - 1) * pageSize,
        take: pageSize
      }),
      prisma.ipRecord.count({ where })
    ]);

    return Response.json({ items, total, page, pageSize });
  } catch (error) {
    const message = error instanceof Error ? error.message : "读取历史失败";
    return jsonError(message, message.includes("未登录") ? 401 : 400);
  }
}
