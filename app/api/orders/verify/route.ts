import { NextRequest } from "next/server";
import { requireUser } from "@/lib/auth";
import { activatePaidOrder } from "@/lib/payment";
import { orderVerifySchema } from "@/lib/validators";
import { assertTrustedOrigin, jsonError } from "@/lib/security";
import { prisma } from "@/lib/db";

const permanentFailures = [
  "格式错误",
  "执行失败",
  "不匹配",
  "未找到符合",
  "金额",
  "付款钱包",
  "已被其它订单",
  "过期"
];

export async function POST(request: NextRequest) {
  let parsed: { orderId: string; txHash: string } | null = null;
  try {
    assertTrustedOrigin(request);
    const user = await requireUser(request);
    parsed = orderVerifySchema.parse(await request.json());
    parsed.txHash = parsed.txHash.toLowerCase();
    const result = await activatePaidOrder(parsed.orderId, user.id, parsed.txHash, user.deviceId);
    return Response.json({
      confirmed: result.confirmed,
      confirmations: result.confirmations,
      required: result.required,
      status: result.confirmed ? "PAID" : "VERIFYING"
    }, { status: result.confirmed ? 200 : 202 });
  } catch (error) {
    const message = error instanceof Error ? error.message : "验单失败";
    if (parsed && permanentFailures.some((item) => message.includes(item))) {
      await prisma.order.updateMany({
        where: { id: parsed.orderId, status: { in: ["PENDING", "VERIFYING"] } },
        data: {
          status: message.includes("过期") ? "EXPIRED" : "REJECTED",
          failureReason: message,
          txHash: message.includes("已被其它订单") ? undefined : parsed.txHash
        }
      });
    }
    return jsonError(message, message.includes("未登录") ? 401 : 400);
  }
}
