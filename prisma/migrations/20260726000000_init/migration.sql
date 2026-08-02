CREATE TYPE "UserRole" AS ENUM ('ADMIN', 'USER');
CREATE TYPE "UserStatus" AS ENUM ('ACTIVE', 'DISABLED');
CREATE TYPE "Exchange" AS ENUM ('BITRUE', 'HOTCOIN', 'MGBX', 'OTHER');

CREATE TABLE "users" (
  "id" TEXT NOT NULL,
  "username" TEXT NOT NULL,
  "password_hash" TEXT NOT NULL,
  "role" "UserRole" NOT NULL DEFAULT 'USER',
  "status" "UserStatus" NOT NULL DEFAULT 'ACTIVE',
  "last_login_at" TIMESTAMP(3),
  "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "updated_at" TIMESTAMP(3) NOT NULL,
  CONSTRAINT "users_pkey" PRIMARY KEY ("id")
);

CREATE TABLE "ip_records" (
  "id" TEXT NOT NULL,
  "full_ip" TEXT NOT NULL,
  "segment_a" INTEGER NOT NULL,
  "segment_b" INTEGER NOT NULL,
  "segment_c" INTEGER NOT NULL,
  "segment_d" INTEGER NOT NULL,
  "exchange" "Exchange" NOT NULL,
  "user_id" TEXT NOT NULL,
  "query_count" INTEGER NOT NULL DEFAULT 1,
  "last_similarity" INTEGER NOT NULL DEFAULT 0,
  "first_seen_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "last_seen_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "updated_at" TIMESTAMP(3) NOT NULL,
  CONSTRAINT "ip_records_pkey" PRIMARY KEY ("id")
);

CREATE TABLE "operation_logs" (
  "id" TEXT NOT NULL,
  "user_id" TEXT,
  "action" TEXT NOT NULL,
  "target_type" TEXT NOT NULL,
  "target_id" TEXT,
  "detail" JSONB,
  "ip_address" TEXT,
  "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT "operation_logs_pkey" PRIMARY KEY ("id")
);

CREATE UNIQUE INDEX "users_username_key" ON "users"("username");
CREATE UNIQUE INDEX "ip_records_full_ip_exchange_key" ON "ip_records"("full_ip", "exchange");
CREATE INDEX "ip_records_full_ip_idx" ON "ip_records"("full_ip");
CREATE INDEX "ip_records_segment_a_idx" ON "ip_records"("segment_a");
CREATE INDEX "ip_records_segment_b_idx" ON "ip_records"("segment_b");
CREATE INDEX "ip_records_segment_c_idx" ON "ip_records"("segment_c");
CREATE INDEX "ip_records_segment_d_idx" ON "ip_records"("segment_d");
CREATE INDEX "ip_records_exchange_idx" ON "ip_records"("exchange");
CREATE INDEX "ip_records_user_id_idx" ON "ip_records"("user_id");
CREATE INDEX "ip_records_last_similarity_idx" ON "ip_records"("last_similarity");
CREATE INDEX "ip_records_created_at_idx" ON "ip_records"("created_at");
CREATE INDEX "operation_logs_user_id_idx" ON "operation_logs"("user_id");
CREATE INDEX "operation_logs_action_idx" ON "operation_logs"("action");
CREATE INDEX "operation_logs_target_type_idx" ON "operation_logs"("target_type");
CREATE INDEX "operation_logs_created_at_idx" ON "operation_logs"("created_at");

ALTER TABLE "ip_records" ADD CONSTRAINT "ip_records_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "users"("id") ON DELETE RESTRICT ON UPDATE CASCADE;
ALTER TABLE "operation_logs" ADD CONSTRAINT "operation_logs_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "users"("id") ON DELETE SET NULL ON UPDATE CASCADE;
