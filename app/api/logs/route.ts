import { NextRequest } from "next/server";
import { prisma } from "@/lib/db";
import { requireOwner } from "@/lib/auth";
import { jsonError } from "@/lib/security";

export async function GET(request: NextRequest) {
  try {
    await requireOwner(request);
    const page = Math.max(1, Number(request.nextUrl.searchParams.get("page") || 1));
    const pageSize = Math.min(100, Math.max(10, Number(request.nextUrl.searchParams.get("pageSize") || 20)));
    const [items, total] = await Promise.all([
      prisma.operationLog.findMany({
        include: { user: { select: { username: true } } },
        orderBy: { createdAt: "desc" },
        skip: (page - 1) * pageSize,
        take: pageSize
      }),
      prisma.operationLog.count()
    ]);
    return Response.json({ items, total, page, pageSize });
  } catch (error) {
    const message = error instanceof Error ? error.message : "读取日志失败";
    return jsonError(message, message.includes("管理员") ? 403 : 401);
  }
}
