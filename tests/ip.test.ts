import { describe, expect, it } from "vitest";
import { compareIpSimilarity, parseIPv4 } from "@/lib/ip";

describe("IPv4 validation", () => {
  it("accepts valid IPv4", () => {
    expect(parseIPv4("192.168.1.10")).toEqual({
      fullIp: "192.168.1.10",
      segmentA: 192,
      segmentB: 168,
      segmentC: 1,
      segmentD: 10
    });
  });

  it("rejects empty input", () => {
    expect(() => parseIPv4("")).toThrow();
  });

  it("rejects invalid IPv4", () => {
    expect(() => parseIPv4("256.1.1.1")).toThrow();
    expect(() => parseIPv4("192.168.001.1")).toThrow();
    expect(() => parseIPv4("192.168.1")).toThrow();
  });
});

describe("IP similarity", () => {
  const current = parseIPv4("192.168.1.10");

  it("calculates 100 percent exact duplicate", () => {
    expect(compareIpSimilarity(current, parseIPv4("192.168.1.10")).similarity).toBe(100);
  });

  it("calculates 75 percent similarity", () => {
    expect(compareIpSimilarity(current, parseIPv4("192.168.2.10")).similarity).toBe(75);
  });

  it("calculates 50 percent similarity", () => {
    expect(compareIpSimilarity(current, parseIPv4("192.168.2.11")).similarity).toBe(50);
  });

  it("calculates 25 percent similarity", () => {
    expect(compareIpSimilarity(current, parseIPv4("192.1.2.11")).similarity).toBe(25);
  });

  it("calculates 0 percent similarity", () => {
    expect(compareIpSimilarity(current, parseIPv4("8.8.8.8")).similarity).toBe(0);
  });
});
