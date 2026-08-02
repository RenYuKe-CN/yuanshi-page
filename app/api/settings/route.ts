import { NextRequest } from "next/server";
import { requireOwner } from "@/lib/auth";
import { jsonError } from "@/lib/security";

export async function GET(request: NextRequest) {
  try {
    await requireOwner(request);
    return Response.json({
      settings: {
        loginRateLimit: Number(process.env.LOGIN_RATE_LIMIT || 5),
        queryRateLimit: Number(process.env.QUERY_RATE_LIMIT || 30),
        trustedOrigin: process.env.TRUSTED_ORIGIN || ""
      }
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : "读取设置失败";
    return jsonError(message, message.includes("管理员") ? 403 : 401);
  }
}
