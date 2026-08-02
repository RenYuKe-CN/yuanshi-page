ALTER TABLE "ip_records"
  ALTER COLUMN "exchange" TYPE TEXT
  USING (
    CASE "exchange"::text
      WHEN 'BITRUE' THEN 'Bitrue'
      WHEN 'HOTCOIN' THEN 'Hotcoin'
      WHEN 'MGBX' THEN 'MGBX'
      WHEN 'OTHER' THEN '其他'
      ELSE "exchange"::text
    END
  );

DROP TYPE "Exchange";
