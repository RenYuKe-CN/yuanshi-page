import { NextRequest } from "next/server";
import { requireOwner } from "@/lib/auth";
import { prisma } from "@/lib/db";
import { announcementSchema } from "@/lib/validators";
import { assertTrustedOrigin, jsonError } from "@/lib/security";

export async function PATCH(request: NextRequest, context: { params: Promise<{ id: string }> }) {
  try {
    assertTrustedOrigin(request);
    await requireOwner(request);
    const { id } = await context.params;
    const body = announcementSchema.partial().parse(await request.json());
    const announcement = await prisma.announcement.update({
      where: { id },
      data: { ...body, expiresAt: body.expiresAt ? new Date(body.expiresAt) : body.expiresAt }
    });
    return Response.json({ announcement });
  } catch (error) {
    return jsonError(error instanceof Error ? error.message : "更新公告失败", 400);
  }
}

export async function DELETE(request: NextRequest, context: { params: Promise<{ id: string }> }) {
  try {
    assertTrustedOrigin(request);
    await requireOwner(request);
    const { id } = await context.params;
    await prisma.announcement.delete({ where: { id } });
    return Response.json({ ok: true });
  } catch (error) {
    return jsonError(error instanceof Error ? error.message : "删除公告失败", 400);
  }
}
