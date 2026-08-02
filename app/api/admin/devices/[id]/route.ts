import { z } from "zod";
import { NextRequest } from "next/server";
import { requireOwner } from "@/lib/auth";
import { prisma } from "@/lib/db";
import { assertTrustedOrigin, jsonError } from "@/lib/security";

const schema = z.object({ action: z.enum(["UNBIND", "BLOCK", "ACTIVATE"]) });

export async function PATCH(request: NextRequest, context: { params: Promise<{ id: string }> }) {
  try {
    assertTrustedOrigin(request);
    const admin = await requireOwner(request);
    const { id } = await context.params;
    const { action } = schema.parse(await request.json());
    const data =
      action === "UNBIND" ? { status: "ACTIVE" as const, boundAt: null } :
      action === "BLOCK" ? { status: "BLOCKED" as const } :
      { status: "ACTIVE" as const };
    const device = await prisma.device.update({ where: { id }, data });
    await prisma.operationLog.create({
      data: { userId: admin.id, action: `DEVICE_${action}`, targetType: "DEVICE", targetId: id, detail: { deviceId: device.deviceId } }
    });
    return Response.json({ device });
  } catch (error) {
    return jsonError(error instanceof Error ? error.message : "更新设备失败", 400);
  }
}
