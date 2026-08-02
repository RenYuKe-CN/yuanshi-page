export const ALLOWED_EMAIL_DOMAINS = [
  "gmail.com",
  "qq.com",
  "outlook.com",
  "hotmail.com",
  "163.com",
  "icloud.com",
  "me.com",
  "yahoo.com",
  "proton.me",
  "protonmail.com",
  "aliyun.com",
  "zoho.com"
] as const;

export const EMAIL_DOMAIN_OPTIONS = ALLOWED_EMAIL_DOMAINS.map((domain) => `@${domain}`);

export function isAllowedEmailDomain(email: string) {
  const domain = email.trim().toLowerCase().split("@").at(-1) || "";
  return ALLOWED_EMAIL_DOMAINS.includes(domain as (typeof ALLOWED_EMAIL_DOMAINS)[number]);
}

