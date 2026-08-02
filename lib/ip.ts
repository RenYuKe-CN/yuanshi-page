export type IpSegments = {
  fullIp: string;
  segmentA: number;
  segmentB: number;
  segmentC: number;
  segmentD: number;
};

export type SegmentMatches = {
  a: boolean;
  b: boolean;
  c: boolean;
  d: boolean;
};

const IPV4_RE = /^(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)\.(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)\.(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)\.(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)$/;

export function parseIPv4(input: string): IpSegments {
  const value = input.trim();
  const match = IPV4_RE.exec(value);
  if (!match) {
    throw new Error("请输入合法 IPv4 地址");
  }

  const [segmentA, segmentB, segmentC, segmentD] = value.split(".").map(Number);
  return { fullIp: value, segmentA, segmentB, segmentC, segmentD };
}

export function compareSegments(current: IpSegments, historical: IpSegments): SegmentMatches {
  return {
    a: current.segmentA === historical.segmentA,
    b: current.segmentB === historical.segmentB,
    c: current.segmentC === historical.segmentC,
    d: current.segmentD === historical.segmentD
  };
}

export function similarityFromMatches(matches: SegmentMatches): number {
  return Object.values(matches).filter(Boolean).length * 25;
}

export function compareIpSimilarity(current: IpSegments, historical: IpSegments) {
  const matches = compareSegments(current, historical);
  return { matches, similarity: similarityFromMatches(matches) };
}
