package com.dylan.agent.capability.document;

import com.dylan.agent.api.contract.runtime.plan.DocumentAgentPlan;
import com.dylan.agent.capability.document.profile.DocumentPlanningProfileProjection;
import com.fasterxml.jackson.databind.ObjectMapper;

import java.util.Objects;

/** Runtime Document plan 与 server-origin frozen profile 的单一 PAI-bound 内部 Raw Plan。 */
public final class DocumentRawPlan extends DocumentAgentPlan {
    private final DocumentProfileBinding profileBinding;
    private final DocumentPlanningProfileProjection serverProfileProjection;

    DocumentRawPlan(DocumentAgentPlan runtimePlan, DocumentProfileBinding profileBinding,
                    DocumentPlanningProfileProjection serverProfileProjection, ObjectMapper mapper) {
        Objects.requireNonNull(runtimePlan, "runtimePlan must not be null");
        setDocument(mapper.convertValue(Objects.requireNonNull(runtimePlan.getDocument()),
                com.dylan.agent.api.plan.AgentDocumentSpec.class));
        this.profileBinding = Objects.requireNonNull(profileBinding);
        this.serverProfileProjection = Objects.requireNonNull(serverProfileProjection);
    }

    public DocumentProfileBinding getProfileBinding() { return profileBinding; }
    public DocumentPlanningProfileProjection getServerProfileProjection() { return serverProfileProjection; }
}
