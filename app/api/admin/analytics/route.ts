import { Prisma } from "@prisma/client";
import { NextRequest } from "next/server";
import { requireOwner } from "@/lib/auth";
import { prisma } from "@/lib/db";
import { jsonError } from "@/lib/security";

type MetricRow = { value: bigint | number | string | null };
type SeriesRow = { day: Date; value: bigint | number | string | null };

function numberValue(row: MetricRow | undefined) {
  return Number(row?.value || 0);
}

export async function GET(request: NextRequest) {
  try {
    await requireOwner(request);
    const [
      revenue, paymentCount, starship, pro, todayQueries, totalQueries,
      active24h, registrations, registrationSeries, activeSeries, querySeries, revenueSeries
    ] = await Promise.all([
      prisma.$queryRaw<MetricRow[]>(Prisma.sql`SELECT COALESCE(SUM(amount), 0)::text AS value FROM orders WHERE status = 'PAID'`),
      prisma.$queryRaw<MetricRow[]>(Prisma.sql`SELECT COUNT(*)::bigint AS value FROM orders WHERE status = 'PAID'`),
      prisma.$queryRaw<MetricRow[]>(Prisma.sql`
        SELECT COUNT(*)::bigint AS value FROM memberships m
        JOIN membership_plans p ON p.id = m.plan_id
        JOIN users u ON u.id = m.user_id
        WHERE m.status = 'ACTIVE' AND p.code = 'STARSHIP'
          AND u.role = 'USER' AND u.deleted_at IS NULL
          AND (m.expires_at IS NULL OR m.expires_at > NOW())
      `),
      prisma.$queryRaw<MetricRow[]>(Prisma.sql`
        SELECT COUNT(*)::bigint AS value FROM memberships m
        JOIN membership_plans p ON p.id = m.plan_id
        JOIN users u ON u.id = m.user_id
        WHERE m.status = 'ACTIVE' AND p.code = 'PRO'
          AND u.role = 'USER' AND u.deleted_at IS NULL
          AND (m.expires_at IS NULL OR m.expires_at > NOW())
      `),
      prisma.$queryRaw<MetricRow[]>(Prisma.sql`SELECT COUNT(*)::bigint AS value FROM operation_logs WHERE action = 'IP_QUERY' AND created_at >= CURRENT_DATE`),
      prisma.$queryRaw<MetricRow[]>(Prisma.sql`SELECT COUNT(*)::bigint AS value FROM operation_logs WHERE action = 'IP_QUERY'`),
      prisma.$queryRaw<MetricRow[]>(Prisma.sql`
        SELECT COUNT(*)::bigint AS value FROM users
        WHERE role = 'USER' AND deleted_at IS NULL
          AND last_login_at >= NOW() - INTERVAL '24 hours'
      `),
      prisma.$queryRaw<MetricRow[]>(Prisma.sql`
        SELECT COUNT(*)::bigint AS value FROM users
        WHERE role = 'USER' AND deleted_at IS NULL
      `),
      prisma.$queryRaw<SeriesRow[]>(Prisma.sql`
        SELECT days.day, COUNT(u.id)::bigint AS value
        FROM generate_series(CURRENT_DATE - INTERVAL '29 days', CURRENT_DATE, INTERVAL '1 day') days(day)
        LEFT JOIN users u ON u.role = 'USER' AND u.deleted_at IS NULL
          AND u.created_at >= days.day AND u.created_at < days.day + INTERVAL '1 day'
        GROUP BY days.day ORDER BY days.day
      `),
      prisma.$queryRaw<SeriesRow[]>(Prisma.sql`
        SELECT days.day, COUNT(DISTINCT u.id)::bigint AS value
        FROM generate_series(CURRENT_DATE - INTERVAL '29 days', CURRENT_DATE, INTERVAL '1 day') days(day)
        LEFT JOIN users u ON u.role = 'USER' AND u.deleted_at IS NULL
          AND u.last_login_at >= days.day AND u.last_login_at < days.day + INTERVAL '1 day'
        GROUP BY days.day ORDER BY days.day
      `),
      prisma.$queryRaw<SeriesRow[]>(Prisma.sql`
        SELECT days.day, COUNT(l.id)::bigint AS value
        FROM generate_series(CURRENT_DATE - INTERVAL '29 days', CURRENT_DATE, INTERVAL '1 day') days(day)
        LEFT JOIN operation_logs l ON l.action = 'IP_QUERY' AND l.created_at >= days.day AND l.created_at < days.day + INTERVAL '1 day'
        GROUP BY days.day ORDER BY days.day
      `),
      prisma.$queryRaw<SeriesRow[]>(Prisma.sql`
        SELECT days.day, COALESCE(SUM(o.amount), 0)::text AS value
        FROM generate_series(CURRENT_DATE - INTERVAL '29 days', CURRENT_DATE, INTERVAL '1 day') days(day)
        LEFT JOIN orders o ON o.status = 'PAID' AND o.paid_at >= days.day AND o.paid_at < days.day + INTERVAL '1 day'
        GROUP BY days.day ORDER BY days.day
      `)
    ]);

    const serialize = (rows: SeriesRow[]) => rows.map((row) => ({
      date: row.day.toISOString().slice(0, 10),
      value: Number(row.value || 0)
    }));
    return Response.json({
      metrics: {
        totalRevenue: numberValue(revenue[0]),
        paymentCount: numberValue(paymentCount[0]),
        starshipMembers: numberValue(starship[0]),
        proMembers: numberValue(pro[0]),
        todayQueries: numberValue(todayQueries[0]),
        totalQueries: numberValue(totalQueries[0]),
        active24h: numberValue(active24h[0]),
        registrations: numberValue(registrations[0])
      },
      series: {
        registrations: serialize(registrationSeries),
        active: serialize(activeSeries),
        queries: serialize(querySeries),
        revenue: serialize(revenueSeries)
      },
      generatedAt: new Date().toISOString()
    }, {
      headers: { "Cache-Control": "private, no-store" }
    });
  } catch (error) {
    return jsonError(error instanceof Error ? error.message : "读取经营数据失败", 403);
  }
}
