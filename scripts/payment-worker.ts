import { prisma } from "../lib/db";
import { activatePaidOrder } from "../lib/payment";

const POLL_MS = Math.max(5_000, Number(process.env.PAYMENT_POLL_MS || 15_000));
const PERMANENT_FAILURES = [
  "格式错误",
  "执行失败",
  "不匹配",
  "未找到符合",
  "金额",
  "付款钱包",
  "已被其它订单",
  "过期"
];

async function runOnce() {
  await prisma.order.updateMany({
    where: {
      status: { in: ["PENDING", "VERIFYING"] },
      expiresAt: { lte: new Date() }
    },
    data: { status: "EXPIRED", failureReason: "订单已过期" }
  });

  const orders = await prisma.order.findMany({
    where: {
      status: "VERIFYING",
      txHash: { not: null },
      expiresAt: { gt: new Date() }
    },
    select: { id: true, userId: true, txHash: true },
    orderBy: { updatedAt: "asc" },
    take: 50
  });

  for (const order of orders) {
    if (!order.txHash) continue;
    try {
      await activatePaidOrder(order.id, order.userId, order.txHash);
    } catch (error) {
      const message = error instanceof Error ? error.message : "后台验单失败";
      console.error(`[payment-worker] ${order.id}: ${message}`);
      if (PERMANENT_FAILURES.some((item) => message.includes(item))) {
        await prisma.order.updateMany({
          where: { id: order.id, status: { in: ["PENDING", "VERIFYING"] } },
          data: {
            status: message.includes("过期") ? "EXPIRED" : "REJECTED",
            failureReason: message
          }
        });
      }
    }
  }
}

async function main() {
  console.log(`[payment-worker] started, interval=${POLL_MS}ms`);
  while (true) {
    try {
      await runOnce();
    } catch (error) {
      console.error("[payment-worker] cycle failed", error);
    }
    await new Promise((resolve) => setTimeout(resolve, POLL_MS));
  }
}

main().finally(async () => prisma.$disconnect());
