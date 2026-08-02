import { NextRequest } from "next/server";
import { requireUser } from "@/lib/auth";
import { fetchContractTickers } from "@/lib/market";
import { jsonError } from "@/lib/security";

export async function GET(request: NextRequest) {
  try {
    await requireUser(request);
    const data = await fetchContractTickers();
    return Response.json({
      ...data,
      generatedAt: new Date().toISOString()
    });
  } catch (error) {
    return jsonError(error instanceof Error ? error.message : "读取实时行情失败", 503);
  }
}

