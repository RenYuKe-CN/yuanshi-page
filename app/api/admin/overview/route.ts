import { NextRequest } from "next/server";
import { requireOwner } from "@/lib/auth";
import { prisma } from "@/lib/db";
import { jsonError } from "@/lib/security";

export async function GET(request: NextRequest) {
  try {
    await requireOwner(request);
    const [plans, users, orders, devices, exchanges, announcements] = await Promise.all([
      prisma.membershipPlan.findMany({ orderBy: { sortOrder: "asc" } }),
      prisma.user.findMany({
        where: { deletedAt: null },
        select: {
          id: true, username: true, email: true, role: true, status: true,
          membership: { include: { plan: true } }
        },
        orderBy: { createdAt: "desc" },
        take: 200
      }),
      prisma.order.findMany({
        include: { user: { select: { username: true } }, plan: { select: { name: true, code: true } } },
        orderBy: { createdAt: "desc" },
        take: 100
      }),
      prisma.device.findMany({
        include: { user: { select: { username: true } } },
        orderBy: { lastSeenAt: "desc" },
        take: 200
      }),
      prisma.exchange.findMany({ orderBy: [{ category: "asc" }, { sortOrder: "asc" }] }),
      prisma.announcement.findMany({ orderBy: { publishedAt: "desc" }, take: 100 })
    ]);
    return Response.json({
      plans: plans.map((item) => ({ ...item, priceUsd: item.priceUsd.toString() })),
      users,
      orders: orders.map((item) => ({ ...item, amount: item.amount.toString() })),
      devices,
      exchanges,
      announcements
    });
  } catch (error) {
    return jsonError(error instanceof Error ? error.message : "读取管理后台失败", 403);
  }
}
