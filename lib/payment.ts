import type { Order, PaymentToken, Prisma } from "@prisma/client";
import { prisma } from "@/lib/db";
import { bindDeviceAfterActivation } from "@/lib/device";
import { addCalendarMonths, membershipReminderAt } from "@/lib/membership";

const TRANSFER_TOPIC =
  "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef";
const ADDRESS_RE = /^0x[a-fA-F0-9]{40}$/;
const HASH_RE = /^0x[a-fA-F0-9]{64}$/;

export const BSC_CHAIN_ID = 56;
export const BSC_CHAIN_HEX = "0x38";
export const PAYMENT_RECEIVER =
  process.env.PAYMENT_RECEIVER || "0x04bCA584834489C26d6474701400c88D954B7782";

export function tokenConfig(token: PaymentToken) {
  const defaults = {
    USDT: {
      contract: "0x55d398326f99059ff775485246999027b3197955",
      decimals: 18
    },
    USDC: {
      contract: "0x8ac76a51cc950d9822d68b83fe1ad97b32cd580d",
      decimals: 18
    }
  };
  const contract =
    process.env[`BSC_${token}_CONTRACT`] || defaults[token].contract;
  const decimals = Number(
    process.env[`BSC_${token}_DECIMALS`] || defaults[token].decimals
  );
  if (!ADDRESS_RE.test(contract) || !Number.isInteger(decimals) || decimals < 0 || decimals > 36) {
    throw new Error(`${token} 支付配置无效`);
  }
  return { contract: contract.toLowerCase(), decimals };
}

export function decimalToUnits(value: string, decimals: number) {
  if (!/^\d+(\.\d+)?$/.test(value)) throw new Error("支付金额格式无效");
  const [whole, fraction = ""] = value.split(".");
  if (fraction.length > decimals) throw new Error("支付金额精度无效");
  return BigInt(`${whole}${fraction.padEnd(decimals, "0")}`);
}

export function encodeBep20Transfer(receiver: string, amount: bigint) {
  if (!ADDRESS_RE.test(receiver)) throw new Error("收款地址配置无效");
  const address = receiver.toLowerCase().slice(2).padStart(64, "0");
  const units = amount.toString(16).padStart(64, "0");
  return `0xa9059cbb${address}${units}`;
}

type RpcReceipt = {
  status: string;
  blockNumber: string;
  transactionHash: string;
  from: string;
  to: string;
  logs: Array<{ address: string; topics: string[]; data: string }>;
};

type RpcBlock = { number: string; timestamp: string };

async function rpc<T>(method: string, params: unknown[]): Promise<T> {
  const endpoint = process.env.BSC_RPC_URL || "https://bsc-dataseed.binance.org";
  const response = await fetch(endpoint, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ jsonrpc: "2.0", id: 1, method, params }),
    cache: "no-store",
    signal: AbortSignal.timeout(12_000)
  });
  if (!response.ok) throw new Error("BSC 节点暂时不可用");
  const payload = (await response.json()) as { result?: T; error?: { message?: string } };
  if (payload.error) throw new Error(payload.error.message || "BSC 节点返回错误");
  if (!payload.result) throw new Error("暂未查询到该交易，请稍后重试");
  return payload.result;
}

function topicAddress(topic: string) {
  return `0x${topic.slice(-40)}`.toLowerCase();
}

export async function inspectBscPayment(order: Order, txHash: string) {
  if (!HASH_RE.test(txHash)) throw new Error("Transaction Hash 格式错误");
  if (!ADDRESS_RE.test(order.receivingAddress)) throw new Error("订单收款地址无效");
  const token = tokenConfig(order.paymentToken);
  const receipt = await rpc<RpcReceipt>("eth_getTransactionReceipt", [txHash]);
  if (receipt.status !== "0x1") throw new Error("链上交易执行失败");
  if (receipt.transactionHash.toLowerCase() !== txHash.toLowerCase()) {
    throw new Error("交易 Hash 不匹配");
  }

  const transfer = receipt.logs.find(
    (log) =>
      log.address.toLowerCase() === token.contract &&
      log.topics[0]?.toLowerCase() === TRANSFER_TOPIC &&
      log.topics.length >= 3 &&
      topicAddress(log.topics[2]) === order.receivingAddress.toLowerCase()
  );
  if (!transfer) throw new Error("未找到符合订单收款地址和 Token 的转账");

  const actualAmount = BigInt(transfer.data || "0x0");
  const expectedAmount = decimalToUnits(order.amount.toString(), token.decimals);
  if (actualAmount !== expectedAmount) throw new Error("链上付款金额与订单金额不一致");

  const payerAddress = topicAddress(transfer.topics[1]);
  if (order.payerAddress && payerAddress !== order.payerAddress.toLowerCase()) {
    throw new Error("付款钱包与订单钱包不一致");
  }

  const currentBlockHex = await rpc<string>("eth_blockNumber", []);
  const confirmations = Number(BigInt(currentBlockHex) - BigInt(receipt.blockNumber) + 1n);
  const required = Math.max(1, Number(process.env.BSC_CONFIRMATIONS || 3));
  const block = await rpc<RpcBlock>("eth_getBlockByNumber", [receipt.blockNumber, false]);
  const paidAt = new Date(Number(BigInt(block.timestamp)) * 1000);
  if (paidAt > order.expiresAt) throw new Error("订单过期后才完成付款");

  return {
    payerAddress,
    confirmations,
    required,
    paidAt,
    confirmed: confirmations >= required
  };
}

export async function activatePaidOrder(
  orderId: string,
  userId: string,
  txHash: string,
  deviceId?: string | null
) {
  const order = await prisma.order.findFirst({
    where: { id: orderId, userId },
    include: { plan: true }
  });
  if (!order) throw new Error("订单不存在");
  if (order.status === "PAID") {
    if (order.txHash?.toLowerCase() !== txHash.toLowerCase()) throw new Error("订单已由其它交易完成");
    return { order, confirmed: true, confirmations: order.confirmations, required: 1 };
  }
  if (order.status === "REJECTED" || order.status === "EXPIRED") throw new Error("订单已失效");

  const duplicate = await prisma.order.findFirst({
    where: { txHash: { equals: txHash, mode: "insensitive" }, id: { not: order.id } }
  });
  if (duplicate) throw new Error("该交易 Hash 已被其它订单使用");

  const inspected = await inspectBscPayment(order, txHash);
  if (!inspected.confirmed) {
    await prisma.order.update({
      where: { id: order.id },
      data: {
        status: "VERIFYING",
        txHash,
        payerAddress: inspected.payerAddress,
        confirmations: inspected.confirmations,
        failureReason: null
      }
    });
    return { order, ...inspected };
  }

  const updated = await prisma.$transaction(async (tx: Prisma.TransactionClient) => {
    const claimed = await tx.order.updateMany({
      where: { id: order.id, status: { in: ["PENDING", "VERIFYING"] } },
      data: {
        status: "PAID",
        txHash: txHash.toLowerCase(),
        payerAddress: inspected.payerAddress,
        confirmations: inspected.confirmations,
        failureReason: null,
        paidAt: inspected.paidAt
      }
    });
    if (claimed.count !== 1) return tx.order.findUniqueOrThrow({ where: { id: order.id } });
    const membership = await tx.membership.findUnique({ where: { userId } });
    const now = new Date();
    const base =
      membership?.status === "ACTIVE" &&
      membership.expiresAt &&
      membership.expiresAt > now
        ? membership.expiresAt
        : now;
    const expiresAt = addCalendarMonths(base, Math.max(1, order.plan.durationMonths));
    const reminderAt = membershipReminderAt(expiresAt);
    const remaining =
      membership?.queryLimit === null
        ? 0
        : Math.max(0, (membership?.queryLimit || 0) - (membership?.queryUsed || 0));
    const nextLimit =
      order.plan.queryLimit === null ? null : remaining + order.plan.queryLimit;

    await tx.membership.upsert({
      where: { userId },
      create: {
        userId,
        planId: order.planId,
        status: "ACTIVE",
        startsAt: now,
        expiresAt,
        reminderAt,
        queryLimit: nextLimit,
        queryUsed: 0
      },
      update: {
        planId: order.planId,
        status: "ACTIVE",
        startsAt: membership?.startsAt || now,
        expiresAt,
        reminderAt,
        queryLimit: nextLimit,
        queryUsed: 0
      }
    });
    await bindDeviceAfterActivation(tx, userId, deviceId);
    const paid = await tx.order.findUniqueOrThrow({ where: { id: order.id } });
    await tx.operationLog.create({
      data: {
        userId,
        action: "ORDER_AUTO_PAID",
        targetType: "ORDER",
        targetId: order.id,
        detail: {
          orderNo: order.orderNo,
          plan: order.plan.code,
          token: order.paymentToken,
          amount: order.amount.toString(),
          txHash
        }
      }
    });
    return paid;
  });

  return { order: updated, ...inspected };
}
