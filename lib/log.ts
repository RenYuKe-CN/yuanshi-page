import { Prisma } from "@prisma/client";
import { prisma } from "@/lib/db";

export async function writeOperationLog(input: {
  userId?: string | null;
  action: string;
  targetType: string;
  targetId?: string | null;
  detail?: Prisma.InputJsonValue;
  ipAddress?: string | null;
}) {
  await prisma.operationLog.create({
    data: {
      userId: input.userId ?? null,
      action: input.action,
      targetType: input.targetType,
      targetId: input.targetId ?? null,
      detail: input.detail ?? Prisma.JsonNull,
      ipAddress: input.ipAddress ?? null
    }
  });
}
