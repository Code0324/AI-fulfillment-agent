import DashboardShell from "@/components/dashboard/DashboardShell";
import FulfillmentWorkflow from "@/components/FulfillmentWorkflow";

export default function FulfillmentPage() {
  return (
    <DashboardShell>
      <div className="space-y-8">
        <div>
          <h1 className="text-3xl font-serif font-bold text-luxury-charcoal mb-2">Fulfillment Pipeline</h1>
          <p className="text-sm text-gray-500">Manage supplier workflow and inventory fulfillment.</p>
        </div>
        <FulfillmentWorkflow />
      </div>
    </DashboardShell>
  );
}
