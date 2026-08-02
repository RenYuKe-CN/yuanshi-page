import { NextRequest } from "next/server";
import { requireOwner, requireUser } from "@/lib/auth";
import { prisma } from "@/lib/db";
import { announcementSchema } from "@/lib/validators";
import { assertTrustedOrigin, jsonError } from "@/lib/security";

export async function GET(request: NextRequest) {
  try {
    const user = await requireUser(request);
    const all = user.isOwner && request.nextUrl.searchParams.get("all") === "1";
    const now = new Date();
    const announcements = await prisma.announcement.findMany({
      where: all ? {} : { active: true, publishedAt: { lte: now }, OR: [{ expiresAt: null }, { expiresAt: { gt: now } }] },
      orderBy: { publishedAt: "desc" },
      take: all ? 100 : 10
    });
    return Response.json({ announcements });
  } catch (error) {
    return jsonError(error instanceof Error ? error.message : "读取公告失败", 401);
  }
}

export async function POST(request: NextRequest) {
  try {
    assertTrustedOrigin(request);
    const admin = await requireOwner(request);
    const body = announcementSchema.parse(await request.json());
    const announcement = await prisma.announcement.create({
      data: {
        ...body,
        expiresAt: body.expiresAt ? new Date(body.expiresAt) : null,
        createdById: admin.id
      }
    });
    return Response.json({ announcement }, { status: 201 });
  } catch (error) {
    return jsonError(error instanceof Error ? error.message : "发布公告失败", 400);
  }
}
