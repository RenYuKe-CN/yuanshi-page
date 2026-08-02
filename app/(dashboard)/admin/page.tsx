import { AdminConsole } from "@/components/admin-console";
import { OwnerOnly } from "@/components/owner-only";

export default function AdminPage() {
  return (
    <OwnerOnly>
      <AdminConsole />
    </OwnerOnly>
  );
}
