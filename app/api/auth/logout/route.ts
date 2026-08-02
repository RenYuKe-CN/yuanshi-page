import { NextRequest } from "next/server";
import { clearSessionCookie, readSessionFromRequest } from "@/lib/auth";
import { assertTrustedOrigin, getClientIp, jsonError } from "@/lib/security";
import { writeOperationLog } from "@/lib/log";

export async function POST(request: NextRequest) {
  try {
    assertTrustedOrigin(request);
    const user = await readSessionFromRequest(request);
    await clearSessionCookie();
    if (user) {
      await writeOperationLog({
        userId: user.id,
        action: "LOGOUT",
        targetType: "USER",
        targetId: user.id,
        ipAddress: getClientIp(request)
      });
    }
    return Response.json({ ok: true });
  } catch {
    return jsonError("退出失败", 400);
  }
}
