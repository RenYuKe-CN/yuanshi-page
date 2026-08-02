ALTER TABLE "users"
  ADD COLUMN "recovery_hash" TEXT,
  ADD COLUMN "is_owner" BOOLEAN NOT NULL DEFAULT false,
  ADD COLUMN "session_version" INTEGER NOT NULL DEFAULT 0,
  ADD COLUMN "deleted_at" TIMESTAMP(3);

UPDATE "users"
SET "is_owner" = true
WHERE "id" = (
  SELECT "id"
  FROM "users"
  WHERE "role" = 'ADMIN'
  ORDER BY "created_at" ASC
  LIMIT 1
);

CREATE INDEX "users_deleted_at_idx" ON "users"("deleted_at");
