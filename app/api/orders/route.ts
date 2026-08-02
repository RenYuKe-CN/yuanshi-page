import crypto from "node:crypto";
import { NextRequest } from "next/server";
import { requireUser } from "@/lib/auth";
import { prisma } from "@/lib/db";
import { orderCreateSchema } from "@/lib/validators";
import { assertTrustedOrigin, jsonError } from "@/lib/security";
import { PAYMENT_RECEIVER, decimalToUnits, encodeBep20Transfer, tokenConfig } from "@/lib/payment";

export async function GET(request: NextRequest) {
  try {
    const user = await requireUser(request);
    await prisma.order.updateMany({
      where: { status: { in: ["PENDING", "VERIFYING"] }, expiresAt: { lte: new Date() } },
      data: { status: "EXPIRED", failureReason: "订单已过期" }
    });
    const orders = await prisma.order.findMany({
      where: user.isOwner && request.nextUrl.searchParams.get("all") === "1" ? {} : { userId: user.id },
      include: { plan: true, user: { select: { username: true } } },
      orderBy: { createdAt: "desc" },
      take: 100
    });
    return Response.json({
      orders: orders.map((order) => ({
        ...order,
        amount: order.amount.toString()
      }))
    });
  } catch (error) {
    return jsonError(error instanceof Error ? error.message : "读取订单失败", 401);
  }
}

export async function POST(request: NextRequest) {
  try {
    assertTrustedOrigin(request);
    const user = await requireUser(request);
    const body = orderCreateSchema.parse(await request.json());
    await prisma.order.updateMany({
      where: { userId: user.id, status: { in: ["PENDING", "VERIFYING"] }, expiresAt: { lte: new Date() } },
      data: { status: "EXPIRED", failureReason: "订单已过期" }
    });
    const plan = await prisma.membershipPlan.findFirst({
      where: { code: body.planCode, active: true }
    });
    if (!plan || plan.code === "FREE") return jsonError("套餐不可购买", 400);
    const existing = await prisma.order.findFirst({
      where: {
        userId: user.id,
        planId: plan.id,
        paymentToken: body.paymentToken,
        status: { in: ["PENDING", "VERIFYING"] },
        expiresAt: { gt: new Date() }
      },
      orderBy: { createdAt: "desc" }
    });
    const order =
      existing ||
      (await prisma.order.create({
        data: {
          orderNo: `YS${Date.now()}${crypto.randomInt(1000, 9999)}`,
          userId: user.id,
          planId: plan.id,
          paymentToken: body.paymentToken,
          amount: plan.priceUsd,
          receivingAddress: PAYMENT_RECEIVER,
          payerAddress: body.payerAddress?.toLowerCase(),
          expiresAt: new Date(Date.now() + 30 * 60_000)
        }
      }));
    const token = tokenConfig(order.paymentToken);
    const units = decimalToUnits(order.amount.toString(), token.decimals);
    return Response.json({
      order: { ...order, amount: order.amount.toString() },
      payment: {
        chainId: 56,
        chainHex: "0x38",
        tokenContract: token.contract,
        tokenDecimals: token.decimals,
        receiver: order.receivingAddress,
        amountUnits: `0x${units.toString(16)}`,
        transferData: encodeBep20Transfer(order.receivingAddress, units)
      }
    }, { status: existing ? 200 : 201 });
  } catch (error) {
    return jsonError(error instanceof Error ? error.message : "创建订单失败", 400);
  }
}
