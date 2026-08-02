import QRCode from "qrcode";
import { NextRequest } from "next/server";
import { requireUser } from "@/lib/auth";
import { jsonError } from "@/lib/security";

export async function GET(request: NextRequest) {
  try {
    await requireUser(request);
    const text = request.nextUrl.searchParams.get("text") || "";
    if (!text || text.length > 500) return jsonError("二维码内容无效", 400);
    const buffer = await QRCode.toBuffer(text, {
      type: "png",
      width: 280,
      margin: 2,
      color: { dark: "#111827", light: "#ffffff" },
      errorCorrectionLevel: "M"
    });
    return new Response(new Uint8Array(buffer), {
      headers: {
        "content-type": "image/png",
        "cache-control": "private, max-age=300",
        "x-content-type-options": "nosniff"
      }
    });
  } catch (error) {
    return jsonError(error instanceof Error ? error.message : "二维码生成失败", 401);
  }
}
