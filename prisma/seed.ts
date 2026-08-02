import bcrypt from "bcryptjs";
import { prisma } from "../lib/db";
import exchangeData from "../data/exchanges.json";

const planSeed = [
  {
    code: "FREE",
    name: "普通用户",
    description: "可注册、登录和浏览系统，不能执行 IP 查询。",
    priceUsd: 0,
    durationDays: 0,
    durationMonths: 0,
    queryLimit: 0,
    unlimitedHistory: false,
    features: ["注册登录", "浏览系统", "联系客服"],
    sortOrder: 0
  },
  {
    code: "STARSHIP",
    name: "星舰会员",
    description: "CEX 与 DEX 合计 10 次查询额度，开通日起一个自然月。",
    priceUsd: 12,
    durationDays: 30,
    durationMonths: 1,
    queryLimit: 10,
    unlimitedHistory: false,
    features: ["全部 CEX", "全部 DEX", "总查询 10 次", "历史记录"],
    sortOrder: 10
  },
  {
    code: "PRO",
    name: "旗舰 PRO",
    description: "每月续费制，开通日起一个自然月内可使用全部功能。",
    priceUsd: 19.9,
    durationDays: 30,
    durationMonths: 1,
    queryLimit: null,
    unlimitedHistory: true,
    features: ["全部交易所", "无限查询", "无限历史", "每月续费使用", "优先客服"],
    sortOrder: 20
  }
] as const;

function slugify(value: string) {
  return value.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "") || `exchange-${Buffer.from(value).toString("hex").slice(0, 20)}`;
}

async function main() {
  const username = process.env.ADMIN_USERNAME || "admin";
  const password = process.env.ADMIN_PASSWORD;
  const recoveryCode = process.env.ADMIN_RECOVERY_CODE;
  if (!password || password.length < 10) {
    throw new Error("ADMIN_PASSWORD 必须至少 10 位");
  }
  if (!recoveryCode || recoveryCode.length < 16) {
    throw new Error("ADMIN_RECOVERY_CODE 必须至少 16 位");
  }

  const [passwordHash, recoveryHash] = await Promise.all([
    bcrypt.hash(password, 12),
    bcrypt.hash(recoveryCode, 12)
  ]);
  const user = await prisma.user.upsert({
    where: { username },
    create: { username, passwordHash, recoveryHash, role: "ADMIN", isOwner: true, status: "ACTIVE" },
    update: { role: "ADMIN", isOwner: true, status: "ACTIVE", deletedAt: null }
  });

  for (const plan of planSeed) {
    const data = { ...plan, features: [...plan.features] };
    await prisma.membershipPlan.upsert({
      where: { code: plan.code },
      create: data,
      update: data
    });
  }

  const freePlan = await prisma.membershipPlan.findUniqueOrThrow({ where: { code: "FREE" } });
  const proPlan = await prisma.membershipPlan.findUniqueOrThrow({ where: { code: "PRO" } });
  const allUsers = await prisma.user.findMany({ select: { id: true, isOwner: true } });
  for (const item of allUsers) {
    await prisma.membership.upsert({
      where: { userId: item.id },
      create: {
        userId: item.id,
        planId: item.isOwner ? proPlan.id : freePlan.id,
        status: item.isOwner ? "ACTIVE" : "FREE",
        queryLimit: item.isOwner ? null : 0,
        startsAt: item.isOwner ? new Date() : null
      },
      update: item.isOwner
        ? { planId: proPlan.id, status: "ACTIVE", queryLimit: null }
        : {}
    });
  }

  let exchangeIndex = 0;
  for (const [category, names] of [
    ["CEX", exchangeData.cex],
    ["DEX", exchangeData.dex],
    ["OTHER", ["其他"]]
  ] as const) {
    for (const name of names) {
      await prisma.exchange.upsert({
        where: { name },
        create: { name, slug: `${slugify(name)}-${exchangeIndex}`, category, sortOrder: exchangeIndex, active: true },
        update: { category, sortOrder: exchangeIndex }
      });
      exchangeIndex += 1;
    }
  }

  const announcementCount = await prisma.announcement.count();
  if (announcementCount === 0) {
    await prisma.announcement.create({
      data: {
        title: "欢迎使用原石金手指 V1.0",
        content: "IP 查重、会员管理与链上自动验单功能现已上线。请妥善保管账号与恢复码。",
        type: "UPDATE",
        active: true,
        popup: true,
        createdById: user.id
      }
    });
  }

  await prisma.operationLog.create({
    data: {
      userId: user.id,
      action: "SEED_ADMIN",
      targetType: "USER",
      targetId: user.id,
      detail: { username }
    }
  });

  console.log(`Admin user ready: ${username}`);
}

main()
  .catch((error) => {
    console.error(error);
    process.exit(1);
  })
  .finally(async () => {
    await prisma.$disconnect();
  });
