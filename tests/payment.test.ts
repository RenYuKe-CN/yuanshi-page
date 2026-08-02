import { describe, expect, it } from "vitest";
import { decimalToUnits, encodeBep20Transfer } from "@/lib/payment";

describe("BEP20 payment encoding", () => {
  it("converts decimal amount without floating point loss", () => {
    expect(decimalToUnits("19.90", 18)).toBe(19_900_000_000_000_000_000n);
  });

  it("encodes transfer(address,uint256)", () => {
    const receiver = "0x04bCA584834489C26d6474701400c88D954B7782";
    const encoded = encodeBep20Transfer(receiver, decimalToUnits("12", 18));
    expect(encoded).toMatch(/^0xa9059cbb[0-9a-f]{128}$/);
    expect(encoded.slice(34, 74)).toBe(receiver.toLowerCase().slice(2));
  });

  it("rejects excessive decimal precision", () => {
    expect(() => decimalToUnits("1.001", 2)).toThrow("精度");
  });
});
