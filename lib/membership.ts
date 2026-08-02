import type { Membership, MembershipPlan, Prisma, UserRole } from "@prisma/client";
import { prisma } from "@/lib/db";

export type MembershipWithPlan = Membership & { plan: MembershipPlan };

export function addCalendarMonths(date: Date, months: number) {
  const result = new Date(date);
  const originalDay = result.getUTCDate();
  result.setUTCDate(1);
  result.setUTCMonth(result.getUTCMonth() + months);
  const lastDay = new Date(
    Date.UTC(result.getUTCFullYear(), result.getUTCMonth() + 1, 0)
  ).getUTCDate();
  result.setUTCDate(Math.min(originalDay, lastDay));
  return result;
}

export function membershipReminderAt(expiresAt: Date) {
  return new Date(expiresAt.getTime() - 86_400_000);
}

export async function getMembership(userId: string): Promise<MembershipWithPlan | null> {
  const membership = await prisma.membership.findUnique({
    where: { userId },
    include: { plan: true }
  });

  if (
    membership?.status === "ACTIVE" &&
    membership.expiresAt &&
    membership.expiresAt.getTime() <= Date.now()
  ) {
    return prisma.membership.update({
      where: { id: membership.id },
      data: { status: "EXPIRED" },
      include: { plan: true }
    });
  }
  return membership;
}

export function remainingQueries(membership: MembershipWithPlan | null) {
  if (!membership || membership.queryLimit === null) return null;
  return Math.max(0, membership.queryLimit - membership.queryUsed);
}

export async function requireQueryMembership(userId: string, role: UserRole) {
  if (role === "ADMIN") return null;
  const membership = await getMembership(userId);
  if (!membership || membership.status !== "ACTIVE" || membership.plan.code === "FREE") {
    throw new Error("当前账号尚未开通会员");
  }
  if (membership.queryLimit !== null && membership.queryUsed >= membership.queryLimit) {
    throw new Error("本月额度已使用完");
  }
  return membership;
}

export async function consumeQueryQuota(
  tx: Prisma.TransactionClient,
  membership: MembershipWithPlan | null
) {
  if (!membership || membership.queryLimit === null) return;
  const updated = await tx.membership.updateMany({
    where: {
      id: membership.id,
      status: "ACTIVE",
      queryUsed: { lt: membership.queryLimit }
    },
    data: { queryUsed: { increment: 1 } }
  });
  if (updated.count !== 1) throw new Error("本月额度已使用完");
}

export function serializeMembership(membership: MembershipWithPlan | null, isAdmin = false) {
  if (isAdmin) {
    return {
      status: "ACTIVE",
      planCode: "ADMIN",
      planName: "管理员",
      expiresAt: null,
      queryLimit: null,
      queryUsed: 0,
      remaining: null,
      unlimited: true
    };
  }
  return {
    status: membership?.status || "FREE",
    planCode: membership?.plan.code || "FREE",
    planName: membership?.plan.name || "普通用户",
    expiresAt: membership?.expiresAt?.toISOString() || null,
    queryLimit: membership?.queryLimit ?? 0,
    queryUsed: membership?.queryUsed ?? 0,
    remaining: remainingQueries(membership),
    unlimited: membership?.queryLimit === null && membership?.status === "ACTIVE"
  };
}
