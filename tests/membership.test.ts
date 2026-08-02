import { describe, expect, it } from "vitest";
import { addCalendarMonths, membershipReminderAt } from "@/lib/membership";

describe("membership billing cycle", () => {
  it("uses the same calendar day for a normal month", () => {
    const started = new Date("2026-07-29T10:00:00.000Z");
    expect(addCalendarMonths(started, 1).toISOString()).toBe("2026-08-29T10:00:00.000Z");
  });

  it("uses the final day when the next month is shorter", () => {
    const started = new Date("2026-01-31T10:00:00.000Z");
    expect(addCalendarMonths(started, 1).toISOString()).toBe("2026-02-28T10:00:00.000Z");
  });

  it("reminds exactly one day before expiration", () => {
    const expiresAt = new Date("2026-08-29T10:00:00.000Z");
    expect(membershipReminderAt(expiresAt).toISOString()).toBe("2026-08-28T10:00:00.000Z");
  });
});
