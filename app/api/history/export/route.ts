import { NextRequest } from "next/server";
import { Prisma } from "@prisma/client";
import { prisma } from "@/lib/db";
import { requireUser } from "@/lib/auth";
import { jsonError } from "@/lib/security";
import ExcelJS from "exceljs";

function csvCell(value: unknown) {
  const text = value == null ? "" : String(value);
  return `"${text.replaceAll('"', '""')}"`;
}

export async function GET(request: NextRequest) {
  try {
    const user = await requireUser(request);
    const params = request.nextUrl.searchParams;
    const where: Prisma.IpRecordWhereInput = {};
    const fullIp = params.get("fullIp")?.trim();
    const exchange = params.get("exchange")?.trim();
    const similarity = params.get("similarity")?.trim();
    if (fullIp) where.fullIp = { contains: fullIp };
    if (exchange) where.exchange = exchange;
    if (similarity) where.lastSimilarity = Number(similarity);
    if (!user.isOwner) where.userId = user.id;

    const items = await prisma.ipRecord.findMany({
      where,
      include: { user: { select: { username: true } } },
      orderBy: { lastSeenAt: "desc" },
      take: 5000
    });

    const rows: (string | number)[][] = [
      ["完整IP", "A", "B", "C", "D", "交易所", "重复率", "查询用户", "查询次数", "首次录入", "最近查询"],
      ...items.map((item) => [
        item.fullIp,
        item.segmentA,
        item.segmentB,
        item.segmentC,
        item.segmentD,
        item.exchange,
        item.lastSimilarity,
        item.user.username,
        item.queryCount,
        item.firstSeenAt.toISOString(),
        item.lastSeenAt.toISOString()
      ])
    ];

    if (params.get("format") === "xlsx") {
      const workbook = new ExcelJS.Workbook();
      workbook.creator = "原石金手指";
      const sheet = workbook.addWorksheet("IP查询历史");
      sheet.addRows(rows);
      sheet.getRow(1).font = { bold: true, color: { argb: "FFFFFFFF" } };
      sheet.getRow(1).fill = { type: "pattern", pattern: "solid", fgColor: { argb: "FF111827" } };
      sheet.columns = [
        { width: 18 }, { width: 8 }, { width: 8 }, { width: 8 }, { width: 8 },
        { width: 24 }, { width: 12 }, { width: 18 }, { width: 12 }, { width: 24 }, { width: 24 }
      ];
      const buffer = await workbook.xlsx.writeBuffer();
      return new Response(buffer, {
        headers: {
          "content-type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
          "content-disposition": 'attachment; filename="ip-history.xlsx"',
          "x-content-type-options": "nosniff"
        }
      });
    }

    const csv = `\uFEFF${rows.map((row) => row.map(csvCell).join(",")).join("\n")}`;
    return new Response(csv, {
      headers: {
        "content-type": "text/csv; charset=utf-8",
        "content-disposition": 'attachment; filename="ip-history.csv"'
      }
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : "导出失败";
    return jsonError(message, message.includes("未登录") ? 401 : 400);
  }
}
