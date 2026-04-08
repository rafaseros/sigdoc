import { createFileRoute } from "@tanstack/react-router";
import { TierCard } from "@/features/subscription/components/TierCard";
import { UsageWidget } from "@/features/usage";

export const Route = createFileRoute("/_authenticated/subscription/")({
  component: SubscriptionPage,
});

function SubscriptionPage() {
  return (
    <div className="space-y-8">
      <div>
        <h2 className="text-2xl font-bold text-[#191c1e]">Suscripción</h2>
        <p className="text-[#434655]">
          Tu plan actual y el uso de recursos
        </p>
      </div>

      <section className="flex flex-wrap gap-4">
        <TierCard />
        <UsageWidget />
      </section>
    </div>
  );
}
