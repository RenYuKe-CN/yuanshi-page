import type { NextRequest } from "next/server";

export function getClientIp(request: NextRequest) {
  return (
    request.headers.get("x-forwarded-for")?.split(",")[0]?.trim() ||
    request.headers.get("x-real-ip") ||
    "unknown"
  );
}

export function assertTrustedOrigin(request: NextRequest) {
  if (request.method === "GET" || request.method === "HEAD" || request.method === "OPTIONS") {
    return;
  }

  const trustedOrigin = process.env.TRUSTED_ORIGIN;
  const origin = request.headers.get("origin");
  const expectedOrigin = trustedOrigin || request.nextUrl.origin;

  if (!origin || origin !== expectedOrigin) {
    throw new Error("非法来源请求");
  }
}

export function jsonError(message: string, status = 400) {
  return Response.json({ error: message }, { status });
}
