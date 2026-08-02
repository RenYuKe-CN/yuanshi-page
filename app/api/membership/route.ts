import { NextRequest } from "next/server";
import { requireUser } from "@/lib/auth";
import { getMembership, serializeMembership } from "@/lib/membership";
import { jsonError } from "@/lib/security";

export async function GET(request: NextRequest) {
  try {
    const user = await requireUser(request);
    const membership = user.role === "ADMIN" ? null : await getMembership(user.id);
    return Response.json({
      membership: serializeMembership(membership, user.role === "ADMIN"),
      reminder:
        membership?.status === "ACTIVE" &&
        membership.reminderAt &&
        membership.reminderAt <= new Date() &&
        (!membership.expiresAt || membership.expiresAt > new Date())
          ? "会员即将到期，请及时续费"
          : null
    });
  } catch (error) {
    return jsonError(error instanceof Error ? error.message : "读取会员失败", 401);
  }
}
