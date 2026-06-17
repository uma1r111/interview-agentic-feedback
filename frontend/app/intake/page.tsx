"use client";
import { useState } from "react";
import AuthGuard from "@/components/AuthGuard";
import IntakeWizard from "@/components/IntakeWizard";
import IntakeQueue from "@/components/IntakeQueue";

export default function IntakePage() {
  return (
    <AuthGuard allowedRoles={["hr"]}>
      {() => <IntakeContent />}
    </AuthGuard>
  );
}

function IntakeContent() {
  const [queueKey, setQueueKey] = useState(0);

  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 340px", gap: 24, alignItems: "start" }}>
      <div>
        <div style={{ marginBottom: 20 }}>
          <h2 style={{ fontSize: 18, fontWeight: 700, margin: 0 }}>➕ Register New Candidate</h2>
          <p style={{ fontSize: 13, color: "var(--muted)", margin: "4px 0 0" }}>
            Complete all three steps to run the evaluation pipeline.
          </p>
        </div>
        <IntakeWizard onEvaluated={() => setQueueKey((k) => k + 1)} />
      </div>
      <IntakeQueue
        refreshKey={queueKey}
        onResume={() => {}}
      />
    </div>
  );
}
