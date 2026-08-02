import { SignJWT, jwtVerify } from "jose";
import { cookies } from "next/headers";
import type { NextRequest } from "next/server";
import type { UserRole } from "@prisma/client";
import { prisma } from "@/lib/db";

const COOKIE_NAME = "ys_jsz_session";

export type SessionUser = {
  id: string;
  username: string;
  role: UserRole;
  isOwner: boolean;
  sessionVersion: number;
  deviceId?: string;
};

function getSecret() {
  const secret = process.env.AUTH_SECRET;
  if (!secret || secret.length < 32) {
    throw new Error("AUTH_SECRET 必须至少 32 个字符");
  }
  return new TextEncoder().encode(secret);
}

export async function createSessionToken(user: SessionUser) {
  return new SignJWT(user)
    .setProtectedHeader({ alg: "HS256" })
    .setIssuedAt()
    .setExpirationTime("8h")
    .sign(getSecret());
}

export async function setSessionCookie(user: SessionUser) {
  const token = await createSessionToken(user);
  const cookieStore = await cookies();
  cookieStore.set(COOKIE_NAME, token, {
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge: 60 * 60 * 8
  });
}

export async function clearSessionCookie() {
  const cookieStore = await cookies();
  cookieStore.delete(COOKIE_NAME);
}

export async function readSessionFromRequest(request: NextRequest): Promise<SessionUser | null> {
  const token = request.cookies.get(COOKIE_NAME)?.value;
  if (!token) return null;

  try {
    const { payload } = await jwtVerify(token, getSecret());
    const userId = String(payload.id || "");
    if (!userId) return null;

    const user = await prisma.user.findUnique({
      where: { id: userId },
      select: { id: true, username: true, role: true, isOwner: true, status: true, sessionVersion: true, deletedAt: true }
    });
    if (!user || user.status !== "ACTIVE" || user.deletedAt || user.sessionVersion !== Number(payload.sessionVersion)) return null;

    return {
      id: user.id,
      username: user.username,
      role: user.role,
      isOwner: user.isOwner,
      sessionVersion: user.sessionVersion,
      deviceId: typeof payload.deviceId === "string" ? payload.deviceId : undefined
    };
  } catch {
    return null;
  }
}

export async function requireUser(request: NextRequest) {
  const user = await readSessionFromRequest(request);
  if (!user) {
    throw new Error("未登录或登录已过期");
  }
  return user;
}

export async function requireAdmin(request: NextRequest) {
  const user = await requireUser(request);
  if (user.role !== "ADMIN") {
    throw new Error("需要管理员权限");
  }
  return user;
}

export async function requireOwner(request: NextRequest) {
  const user = await requireAdmin(request);
  if (!user.isOwner) {
    throw new Error("需要总管理员权限");
  }
  return user;
}
