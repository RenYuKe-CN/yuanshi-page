import { NextRequest } from "next/server";
import { readSessionFromRequest } from "@/lib/auth";
import { getMembership, serializeMembership } from "@/lib/membership";
import { prisma } from "@/lib/db";

export async function GET(request: NextRequest) {
  const user = await readSessionFromRequest(request);
  if (!user) return Response.json({ user: null });
  const [membership, device] = await Promise.all([
    user.role === "ADMIN" ? null : getMembership(user.id),
    user.deviceId ? prisma.device.findUnique({
      where: { deviceId: user.deviceId },
      select: { deviceId: true, browser: true, os: true, status: true, boundAt: true, lastSeenAt: true }
    }) : null
  ]);
  return Response.json({
    user,
    membership: serializeMembership(membership, user.role === "ADMIN"),
    device,
    reminder:
      membership?.status === "ACTIVE" &&
      membership.reminderAt &&
      membership.reminderAt <= new Date() &&
      (!membership.expiresAt || membership.expiresAt > new Date())
        ? "会员将在一天内到期，请及时续费"
        : null
  });
}
