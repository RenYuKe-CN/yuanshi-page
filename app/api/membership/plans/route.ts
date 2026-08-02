import { NextRequest } from "next/server";
import { requireUser } from "@/lib/auth";
import { prisma } from "@/lib/db";
import { PAYMENT_RECEIVER, tokenConfig } from "@/lib/payment";
import { jsonError } from "@/lib/security";

export async function GET(request: NextRequest) {
  try {
    await requireUser(request);
    const plans = await prisma.membershipPlan.findMany({
      where: { active: true },
      orderBy: { sortOrder: "asc" }
    });
    return Response.json({
      plans: plans.map((plan) => ({
        ...plan,
        description: plan.code === "PRO" ? "每月续费制，开通日起一个自然月内可使用全部功能。" : plan.description,
        features: plan.code === "PRO" ? ["全部交易所", "无限查询", "无限历史", "每月续费使用", "优先客服"] : plan.features,
        priceUsd: plan.priceUsd.toString()
      })),
      payment: {
        chain: "BSC",
        chainId: 56,
        receiver: PAYMENT_RECEIVER,
        tokens: {
          USDT: tokenConfig("USDT"),
          USDC: tokenConfig("USDC")
        }
      }
    });
  } catch (error) {
    return jsonError(error instanceof Error ? error.message : "读取套餐失败", 401);
  }
}
