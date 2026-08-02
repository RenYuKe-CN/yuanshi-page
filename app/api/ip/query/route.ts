import { Prisma } from "@prisma/client";
import { NextRequest } from "next/server";
import { prisma } from "@/lib/db";
import { requireUser } from "@/lib/auth";
import { ipQuerySchema } from "@/lib/validators";
import { parseIPv4 } from "@/lib/ip";
import { checkRateLimit } from "@/lib/rate-limit";
import { assertTrustedOrigin, getClientIp, jsonError } from "@/lib/security";
import { writeOperationLog } from "@/lib/log";
import { consumeQueryQuota, requireQueryMembership } from "@/lib/membership";
import { enforceMembershipDevice } from "@/lib/device";
import { EXCHANGE_SET } from "@/lib/constants";

type SimilarRecord = {
  id: string;
  fullIp: string;
  segmentA: number;
  segmentB: number;
  segmentC: number;
  segmentD: number;
  exchange: string;
  queryCount: number;
  firstSeenAt: Date;
  lastSeenAt: Date;
  createdAt: Date;
  username: string;
  matchA: boolean;
  matchB: boolean;
  matchC: boolean;
  matchD: boolean;
  similarity: number;
};

export async function POST(request: NextRequest) {
  try {
    assertTrustedOrigin(request);
    const user = await requireUser(request);
    const clientIp = getClientIp(request);
    const limit = Number(process.env.QUERY_RATE_LIMIT || 30);
    const rate = checkRateLimit(`query:${user.id}:${clientIp}`, limit, 60_000);
    if (!rate.ok) return jsonError("查询过于频繁，请稍后再试", 429);

    const body = ipQuerySchema.parse(await request.json());
    const exchangeCount = await prisma.exchange.count();
    const exchangeValid = exchangeCount
      ? Boolean(await prisma.exchange.findFirst({ where: { name: body.exchange, active: true }, select: { id: true } }))
      : EXCHANGE_SET.has(body.exchange);
    if (!exchangeValid) return jsonError("请选择有效的交易所", 400);
    const parsed = parseIPv4(body.ip);
    const now = new Date();
    const membership = await requireQueryMembership(user.id, user.role);
    if (membership) await enforceMembershipDevice(user.id, user.deviceId);
    const existingSubmission = await prisma.ipRecord.findUnique({
      where: {
        ip_records_full_ip_exchange_key: {
          fullIp: parsed.fullIp,
          exchange: body.exchange
        }
      }
    });
    const deduplicated = Boolean(
      existingSubmission &&
      existingSubmission.userId === user.id &&
      now.getTime() - existingSubmission.lastSeenAt.getTime() < 5_000
    );

    const similarPositive = await prisma.$queryRaw<SimilarRecord[]>(Prisma.sql`
      SELECT
        r.id,
        r.full_ip AS "fullIp",
        r.segment_a AS "segmentA",
        r.segment_b AS "segmentB",
        r.segment_c AS "segmentC",
        r.segment_d AS "segmentD",
        r.exchange::text AS exchange,
        r.query_count AS "queryCount",
        r.first_seen_at AS "firstSeenAt",
        r.last_seen_at AS "lastSeenAt",
        r.created_at AS "createdAt",
        u.username,
        (r.segment_a = ${parsed.segmentA}) AS "matchA",
        (r.segment_b = ${parsed.segmentB}) AS "matchB",
        (r.segment_c = ${parsed.segmentC}) AS "matchC",
        (r.segment_d = ${parsed.segmentD}) AS "matchD",
        (
          CASE WHEN r.segment_a = ${parsed.segmentA} THEN 25 ELSE 0 END +
          CASE WHEN r.segment_b = ${parsed.segmentB} THEN 25 ELSE 0 END +
          CASE WHEN r.segment_c = ${parsed.segmentC} THEN 25 ELSE 0 END +
          CASE WHEN r.segment_d = ${parsed.segmentD} THEN 25 ELSE 0 END
        ) AS similarity
      FROM ip_records r
      JOIN users u ON u.id = r.user_id
      WHERE
        r.segment_a = ${parsed.segmentA} OR
        r.segment_b = ${parsed.segmentB} OR
        r.segment_c = ${parsed.segmentC} OR
        r.segment_d = ${parsed.segmentD}
      ORDER BY similarity DESC, r.last_seen_at DESC
      LIMIT 20
    `);
    const zeroRecords =
      similarPositive.length < 20
        ? await prisma.ipRecord.findMany({
            where: { id: { notIn: similarPositive.map((item) => item.id) } },
            include: { user: { select: { username: true } } },
            orderBy: { lastSeenAt: "desc" },
            take: 20 - similarPositive.length
          })
        : [];
    const similarBefore: SimilarRecord[] = [
      ...similarPositive,
      ...zeroRecords.map((item) => ({
        id: item.id,
        fullIp: item.fullIp,
        segmentA: item.segmentA,
        segmentB: item.segmentB,
        segmentC: item.segmentC,
        segmentD: item.segmentD,
        exchange: item.exchange,
        queryCount: item.queryCount,
        firstSeenAt: item.firstSeenAt,
        lastSeenAt: item.lastSeenAt,
        createdAt: item.createdAt,
        username: item.user.username,
        matchA: false,
        matchB: false,
        matchC: false,
        matchD: false,
        similarity: 0
      }))
    ];

    const exactBefore = similarBefore.find((item) => item.fullIp === parsed.fullIp);
    const topSimilarity = similarBefore[0]?.similarity ?? 0;

    const saved = deduplicated && existingSubmission ? existingSubmission : await prisma.$transaction(async (tx) => {
      await consumeQueryQuota(tx, membership);
      return tx.ipRecord.upsert({
        where: {
          ip_records_full_ip_exchange_key: {
            fullIp: parsed.fullIp,
            exchange: body.exchange
          }
        },
        create: {
          fullIp: parsed.fullIp,
          segmentA: parsed.segmentA,
          segmentB: parsed.segmentB,
          segmentC: parsed.segmentC,
          segmentD: parsed.segmentD,
          exchange: body.exchange,
          userId: user.id,
          queryCount: 1,
          lastSimilarity: topSimilarity,
          firstSeenAt: now,
          lastSeenAt: now
        },
        update: {
          queryCount: { increment: 1 },
          lastSimilarity: topSimilarity,
          lastSeenAt: now
        }
      });
    });

    if (!deduplicated) {
      await writeOperationLog({
        userId: user.id,
        action: "IP_QUERY",
        targetType: "IP_RECORD",
        targetId: saved.id,
        detail: { fullIp: parsed.fullIp, exchange: body.exchange },
        ipAddress: clientIp
      });
    }

    return Response.json({
      current: { ...parsed, exchange: body.exchange },
      exactDuplicate: Boolean(exactBefore),
      topSimilarity,
      bestMatch: similarBefore[0] ?? null,
      similarities: similarBefore,
      savedRecord: saved,
      deduplicated
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : "查询失败";
    const status = message.includes("未登录") ? 401 : message.includes("会员") || message.includes("额度") || message.includes("设备") ? 403 : 400;
    return jsonError(message, status);
  }
}
