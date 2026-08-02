import { describe, expect, it } from "vitest";
import { registerSchema } from "@/lib/validators";

const base = {
  username: "operator01",
  password: "StrongPass!123",
  confirmPassword: "StrongPass!123",
  acceptedStatement: true
};

describe("registration email allow-list", () => {
  it("accepts the required mainstream email providers", () => {
    for (const domain of ["gmail.com", "qq.com", "outlook.com", "163.com", "icloud.com", "yahoo.com", "proton.me", "aliyun.com", "zoho.com"]) {
      expect(registerSchema.parse({ ...base, email: `user@${domain}` }).email).toBe(`user@${domain}`);
    }
  });

  it("rejects non-allow-listed email providers", () => {
    expect(() => registerSchema.parse({ ...base, email: "user@example.com" })).toThrow("主流邮箱");
  });

  it("requires the registration statement checkbox", () => {
    expect(() => registerSchema.parse({ ...base, email: "user@gmail.com", acceptedStatement: false })).toThrow("用户注册声明");
  });
});

