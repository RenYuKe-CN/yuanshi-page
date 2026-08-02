import exchangeData from "@/data/exchanges.json";

export const CEX_EXCHANGES = exchangeData.cex as readonly string[];
export const DEX_EXCHANGES = exchangeData.dex as readonly string[];
export const EXCHANGE_GROUPS = [
  { label: "CEX 中心化交易所", items: CEX_EXCHANGES },
  { label: "DEX 去中心化交易所", items: DEX_EXCHANGES },
  { label: "其他", items: ["其他"] }
] as const;
export const EXCHANGES = [...CEX_EXCHANGES, ...DEX_EXCHANGES, "其他"] as const;
export const EXCHANGE_SET = new Set<string>(EXCHANGES);

const LEGACY_EXCHANGE_LABELS: Record<string, string> = {
  BITRUE: "Bitrue",
  HOTCOIN: "Hotcoin",
  MGBX: "MGBX",
  OTHER: "其他"
};

export function exchangeLabel(value: string) {
  return LEGACY_EXCHANGE_LABELS[value] || value;
}

export const SIMILARITY_LABELS: Record<number, string> = {
  100: "精确重复",
  75: "高度相似",
  50: "中度相似",
  25: "低度相似",
  0: "未发现相似"
};
