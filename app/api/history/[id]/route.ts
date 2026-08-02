import { NextRequest } from "next/server";
import { prisma } from "@/lib/db";
import { requireOwner } from "@/lib/auth";
import { assertTrustedOrigin, getClientIp, jsonError } from "@/lib/security";
import { writeOperationLog } from "@/lib/log";

export async function DELETE(request: NextRequest, context: { params: Promise<{ id: string }> }) {
  try {
    assertTrustedOrigin(request);
    const user = await requireOwner(request);
    const { id } = await context.params;
    const deleted = await prisma.ipRecord.delete({ where: { id } });
    await writeOperationLog({
      userId: user.id,
      action: "DELETE_IP_RECORD",
      targetType: "IP_RECORD",
      targetId: id,
      detail: { fullIp: deleted.fullIp, exchange: deleted.exchange },
      ipAddress: getClientIp(request)
    });
    return Response.json({ ok: true });
  } catch (error) {
    const message = error instanceof Error ? error.message : "删除失败";
    return jsonError(message, message.includes("管理员") ? 403 : 400);
  }
}
