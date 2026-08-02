export type MarketTicker = {
  symbol: "BTC-USDT" | "ETH-USDT" | "SOL-USDT" | "BNB-USDT" | "OKB-USDT";
  base: "BTC" | "ETH" | "SOL" | "BNB" | "OKB";
  venue: "OKX" | "Binance" | "CMC";
  marketType: "SWAP" | "SPOT" | "QUOTE";
  price: number;
  indexPrice: number | null;
  change24h: number | null;
  high24h: number | null;
  low24h: number | null;
  volume24h: number | null;
  updatedAt: string;
};

type OkxTicker = {
  instId: string;
  last: string;
  sodUtc0: string;
  high24h: string;
  low24h: string;
  volCcy24h: string;
  ts: string;
};

type OkxMark = {
  instId: string;
  markPx: string;
  ts: string;
};

type BinanceTicker = {
  symbol: string;
  lastPrice: string;
  priceChangePercent: string;
  highPrice: string;
  lowPrice: string;
  volume: string;
  closeTime: number;
};

type CmcQuote = {
  data: Record<string, {
    symbol: string;
    quote: {
      USD: {
        price: number;
        percent_change_24h: number | null;
        volume_24h: number | null;
        last_updated: string;
      };
    };
  }>;
};

const MARKET_PAIRS = [
  { symbol: "BTC-USDT", base: "BTC", okxSwap: "BTC-USDT-SWAP", okxSpot: "BTC-USDT", binance: "BTCUSDT" },
  { symbol: "ETH-USDT", base: "ETH", okxSwap: "ETH-USDT-SWAP", okxSpot: "ETH-USDT", binance: "ETHUSDT" },
  { symbol: "SOL-USDT", base: "SOL", okxSwap: "SOL-USDT-SWAP", okxSpot: "SOL-USDT", binance: "SOLUSDT" },
  { symbol: "BNB-USDT", base: "BNB", okxSwap: "BNB-USDT-SWAP", okxSpot: "BNB-USDT", binance: "BNBUSDT" },
  { symbol: "OKB-USDT", base: "OKB", okxSwap: "OKB-USDT-SWAP", okxSpot: "OKB-USDT", binance: null }
] as const;

function numberOrNull(value: unknown) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function changePercent(price: number, open: number | null) {
  if (!open || open <= 0) return null;
  return ((price - open) / open) * 100;
}

async function fetchJson<T>(url: string): Promise<T> {
  const response = await fetch(url, {
    cache: "no-store",
    headers: { "user-agent": "Yuanshi-Jinshouzhi/1.0" },
    signal: AbortSignal.timeout(8_000)
  });
  if (!response.ok) throw new Error(`行情接口异常：${response.status}`);
  return response.json() as Promise<T>;
}

export async function fetchOkxTickers(): Promise<MarketTicker[]> {
  const [swapPayload, spotPayload, markPayload] = await Promise.all([
    fetchJson<{ data: OkxTicker[] }>("https://www.okx.com/api/v5/market/tickers?instType=SWAP"),
    fetchJson<{ data: OkxTicker[] }>("https://www.okx.com/api/v5/market/tickers?instType=SPOT"),
    fetchJson<{ data: OkxMark[] }>("https://www.okx.com/api/v5/public/mark-price?instType=SWAP")
  ]);
  return MARKET_PAIRS.map((pair) => {
    const swapTicker = swapPayload.data.find((item) => item.instId === pair.okxSwap);
    const mark = markPayload.data.find((item) => item.instId === pair.okxSwap);
    const spotTicker = spotPayload.data.find((item) => item.instId === pair.okxSpot);
    const ticker = swapTicker || spotTicker;
    const price = numberOrNull(ticker?.last) ?? numberOrNull(mark?.markPx);
    if (!price) return null;
    const open = numberOrNull(ticker?.sodUtc0);
    return {
      symbol: pair.symbol,
      base: pair.base,
      venue: "OKX",
      marketType: swapTicker ? "SWAP" : "SPOT",
      price,
      indexPrice: numberOrNull(ticker?.last),
      change24h: changePercent(price, open),
      high24h: numberOrNull(ticker?.high24h),
      low24h: numberOrNull(ticker?.low24h),
      volume24h: numberOrNull(ticker?.volCcy24h),
      updatedAt: new Date(Number(mark?.ts || ticker?.ts || Date.now())).toISOString()
    };
  }).filter(Boolean) as MarketTicker[];
}

export async function fetchBinanceFallbackTickers(): Promise<MarketTicker[]> {
  const tickerPayload = await fetchJson<BinanceTicker[]>("https://api.binance.com/api/v3/ticker/24hr");
  return MARKET_PAIRS.filter((pair) => pair.binance).map((pair) => {
    const ticker = tickerPayload.find((entry) => entry.symbol === pair.binance);
    const price = numberOrNull(ticker?.lastPrice);
    if (!price) throw new Error(`Binance ${pair.binance} 行情缺失`);
    return {
      symbol: pair.symbol,
      base: pair.base,
      venue: "Binance",
      marketType: "SPOT",
      price,
      indexPrice: price,
      change24h: numberOrNull(ticker?.priceChangePercent),
      high24h: numberOrNull(ticker?.highPrice),
      low24h: numberOrNull(ticker?.lowPrice),
      volume24h: numberOrNull(ticker?.volume),
      updatedAt: new Date(ticker?.closeTime || Date.now()).toISOString()
    };
  });
}

export async function fetchCmcFallbackTickers(): Promise<MarketTicker[]> {
  const apiKey = process.env.CMC_API_KEY || process.env.COINMARKETCAP_API_KEY;
  if (!apiKey) throw new Error("CMC API Key 未配置");
  const response = await fetch("https://pro-api.coinmarketcap.com/v2/cryptocurrency/quotes/latest?symbol=BTC,ETH,SOL,BNB,OKB&convert=USD", {
    cache: "no-store",
    headers: {
      "X-CMC_PRO_API_KEY": apiKey,
      "user-agent": "Yuanshi-Jinshouzhi/1.0"
    },
    signal: AbortSignal.timeout(8_000)
  });
  if (!response.ok) throw new Error("CMC 行情接口异常");
  const payload = await response.json() as CmcQuote;
  return MARKET_PAIRS.map((pair) => {
    const quote = payload.data[pair.base]?.quote.USD;
    if (!quote?.price) throw new Error(`CMC ${pair.base} 行情缺失`);
    return {
      symbol: pair.symbol,
      base: pair.base,
      venue: "CMC",
      marketType: "QUOTE",
      price: quote.price,
      indexPrice: null,
      change24h: quote.percent_change_24h,
      high24h: null,
      low24h: null,
      volume24h: quote.volume_24h,
      updatedAt: quote.last_updated
    };
  });
}

export async function fetchContractTickers() {
  const binance = await fetchBinanceFallbackTickers().catch(() => []);
  const cmc = await fetchCmcFallbackTickers().catch(() => []);
  const okx = await fetchOkxTickers().catch(() => []);
  const merged = MARKET_PAIRS.map((pair) => (
    binance.find((item) => item.symbol === pair.symbol) ||
    cmc.find((item) => item.symbol === pair.symbol) ||
    okx.find((item) => item.symbol === pair.symbol)
  )).filter(Boolean) as MarketTicker[];
  if (!merged.length) throw new Error("实时行情暂时无法连接");
  const sources = Array.from(new Set(merged.map((item) => item.venue)));
  return { source: sources.join(" + "), items: merged };
}
