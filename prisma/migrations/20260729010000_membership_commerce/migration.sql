-- 原石金手指 V1.0：会员、订单、设备、交易所与公告
CREATE TYPE "MembershipStatus" AS ENUM ('FREE', 'ACTIVE', 'EXPIRED', 'SUSPENDED');
CREATE TYPE "OrderStatus" AS ENUM ('PENDING', 'VERIFYING', 'PAID', 'REJECTED', 'EXPIRED');
CREATE TYPE "PaymentToken" AS ENUM ('USDT', 'USDC');
CREATE TYPE "DeviceStatus" AS ENUM ('ACTIVE', 'BLOCKED', 'UNBOUND');
CREATE TYPE "ExchangeCategory" AS ENUM ('CEX', 'DEX', 'OTHER');
CREATE TYPE "AnnouncementType" AS ENUM ('NOTICE', 'MAINTENANCE', 'UPDATE', 'ACTIVITY');

ALTER TABLE "users" ADD COLUMN "email" TEXT;
CREATE UNIQUE INDEX "users_email_key" ON "users"("email");

CREATE TABLE "membership_plans" (
  "id" TEXT NOT NULL,
  "code" TEXT NOT NULL,
  "name" TEXT NOT NULL,
  "description" TEXT,
  "price_usd" DECIMAL(10,2) NOT NULL,
  "duration_days" INTEGER NOT NULL DEFAULT 30,
  "duration_months" INTEGER NOT NULL DEFAULT 1,
  "query_limit" INTEGER,
  "unlimited_history" BOOLEAN NOT NULL DEFAULT false,
  "features" JSONB NOT NULL,
  "active" BOOLEAN NOT NULL DEFAULT true,
  "sort_order" INTEGER NOT NULL DEFAULT 0,
  "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "updated_at" TIMESTAMP(3) NOT NULL,
  CONSTRAINT "membership_plans_pkey" PRIMARY KEY ("id")
);

CREATE TABLE "memberships" (
  "id" TEXT NOT NULL,
  "user_id" TEXT NOT NULL,
  "plan_id" TEXT NOT NULL,
  "status" "MembershipStatus" NOT NULL DEFAULT 'FREE',
  "starts_at" TIMESTAMP(3),
  "expires_at" TIMESTAMP(3),
  "reminder_at" TIMESTAMP(3),
  "query_limit" INTEGER,
  "query_used" INTEGER NOT NULL DEFAULT 0,
  "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "updated_at" TIMESTAMP(3) NOT NULL,
  CONSTRAINT "memberships_pkey" PRIMARY KEY ("id")
);

CREATE TABLE "orders" (
  "id" TEXT NOT NULL,
  "order_no" TEXT NOT NULL,
  "user_id" TEXT NOT NULL,
  "plan_id" TEXT NOT NULL,
  "status" "OrderStatus" NOT NULL DEFAULT 'PENDING',
  "payment_token" "PaymentToken" NOT NULL,
  "chain" TEXT NOT NULL DEFAULT 'BSC',
  "amount" DECIMAL(10,2) NOT NULL,
  "receiving_address" TEXT NOT NULL,
  "payer_address" TEXT,
  "tx_hash" TEXT,
  "confirmations" INTEGER NOT NULL DEFAULT 0,
  "failure_reason" TEXT,
  "expires_at" TIMESTAMP(3) NOT NULL,
  "paid_at" TIMESTAMP(3),
  "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "updated_at" TIMESTAMP(3) NOT NULL,
  CONSTRAINT "orders_pkey" PRIMARY KEY ("id")
);

CREATE TABLE "devices" (
  "id" TEXT NOT NULL,
  "user_id" TEXT NOT NULL,
  "device_id" TEXT NOT NULL,
  "fingerprint_hash" TEXT NOT NULL,
  "browser" TEXT,
  "os" TEXT,
  "user_agent" TEXT,
  "ip_address" TEXT,
  "status" "DeviceStatus" NOT NULL DEFAULT 'ACTIVE',
  "bound_at" TIMESTAMP(3),
  "first_seen_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "last_seen_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "updated_at" TIMESTAMP(3) NOT NULL,
  CONSTRAINT "devices_pkey" PRIMARY KEY ("id")
);

CREATE TABLE "exchanges" (
  "id" TEXT NOT NULL,
  "slug" TEXT NOT NULL,
  "name" TEXT NOT NULL,
  "category" "ExchangeCategory" NOT NULL,
  "icon_url" TEXT,
  "active" BOOLEAN NOT NULL DEFAULT true,
  "sort_order" INTEGER NOT NULL DEFAULT 0,
  "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "updated_at" TIMESTAMP(3) NOT NULL,
  CONSTRAINT "exchanges_pkey" PRIMARY KEY ("id")
);

CREATE TABLE "announcements" (
  "id" TEXT NOT NULL,
  "title" TEXT NOT NULL,
  "content" TEXT NOT NULL,
  "type" "AnnouncementType" NOT NULL DEFAULT 'NOTICE',
  "active" BOOLEAN NOT NULL DEFAULT true,
  "popup" BOOLEAN NOT NULL DEFAULT false,
  "published_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "expires_at" TIMESTAMP(3),
  "created_by_id" TEXT,
  "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "updated_at" TIMESTAMP(3) NOT NULL,
  CONSTRAINT "announcements_pkey" PRIMARY KEY ("id")
);

CREATE TABLE "system_settings" (
  "key" TEXT NOT NULL,
  "value" JSONB NOT NULL,
  "updated_at" TIMESTAMP(3) NOT NULL,
  CONSTRAINT "system_settings_pkey" PRIMARY KEY ("key")
);

CREATE UNIQUE INDEX "membership_plans_code_key" ON "membership_plans"("code");
CREATE INDEX "membership_plans_active_sort_order_idx" ON "membership_plans"("active", "sort_order");
CREATE UNIQUE INDEX "memberships_user_id_key" ON "memberships"("user_id");
CREATE INDEX "memberships_status_expires_at_idx" ON "memberships"("status", "expires_at");
CREATE UNIQUE INDEX "orders_order_no_key" ON "orders"("order_no");
CREATE UNIQUE INDEX "orders_tx_hash_key" ON "orders"("tx_hash");
CREATE INDEX "orders_user_id_created_at_idx" ON "orders"("user_id", "created_at");
CREATE INDEX "orders_status_expires_at_idx" ON "orders"("status", "expires_at");
CREATE INDEX "orders_payment_token_idx" ON "orders"("payment_token");
CREATE UNIQUE INDEX "devices_device_id_key" ON "devices"("device_id");
CREATE UNIQUE INDEX "devices_user_id_fingerprint_hash_key" ON "devices"("user_id", "fingerprint_hash");
CREATE INDEX "devices_user_id_status_idx" ON "devices"("user_id", "status");
CREATE INDEX "devices_fingerprint_hash_idx" ON "devices"("fingerprint_hash");
CREATE UNIQUE INDEX "exchanges_slug_key" ON "exchanges"("slug");
CREATE UNIQUE INDEX "exchanges_name_key" ON "exchanges"("name");
CREATE INDEX "exchanges_category_active_sort_order_idx" ON "exchanges"("category", "active", "sort_order");
CREATE INDEX "announcements_active_published_at_idx" ON "announcements"("active", "published_at");

ALTER TABLE "memberships" ADD CONSTRAINT "memberships_user_id_fkey"
  FOREIGN KEY ("user_id") REFERENCES "users"("id") ON DELETE RESTRICT ON UPDATE CASCADE;
ALTER TABLE "memberships" ADD CONSTRAINT "memberships_plan_id_fkey"
  FOREIGN KEY ("plan_id") REFERENCES "membership_plans"("id") ON DELETE RESTRICT ON UPDATE CASCADE;
ALTER TABLE "orders" ADD CONSTRAINT "orders_user_id_fkey"
  FOREIGN KEY ("user_id") REFERENCES "users"("id") ON DELETE RESTRICT ON UPDATE CASCADE;
ALTER TABLE "orders" ADD CONSTRAINT "orders_plan_id_fkey"
  FOREIGN KEY ("plan_id") REFERENCES "membership_plans"("id") ON DELETE RESTRICT ON UPDATE CASCADE;
ALTER TABLE "devices" ADD CONSTRAINT "devices_user_id_fkey"
  FOREIGN KEY ("user_id") REFERENCES "users"("id") ON DELETE RESTRICT ON UPDATE CASCADE;
ALTER TABLE "announcements" ADD CONSTRAINT "announcements_created_by_id_fkey"
  FOREIGN KEY ("created_by_id") REFERENCES "users"("id") ON DELETE SET NULL ON UPDATE CASCADE;
