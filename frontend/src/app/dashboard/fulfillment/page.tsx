import DashboardShell from "@/components/dashboard/DashboardShell";
import FulfillmentWorkflow from "@/components/FulfillmentWorkflow";
import MockAmazonOrders from "@/components/MockAmazonOrders";

export default function FulfillmentPage() {
  return (
    <DashboardShell>
      <div className="space-y-8">
        <FulfillmentWorkflow />
        <hr className="border-gray-200" />
        <MockAmazonOrders />
      </div>
    </DashboardShell>
  );
}
