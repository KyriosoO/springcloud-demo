package com.dylan.agent.metadata.context.port;

import com.dylan.agent.api.contract.runtime.common.RuntimeContextView;
import com.dylan.agent.kernel.definition.ContextReadDeclaration;
import com.dylan.agent.metadata.authorization.model.PlanningAuthorizationEvidence;
import com.dylan.agent.metadata.context.model.ContextSnapshot;
import com.dylan.agent.metadata.context.request.ContextReadRequest;

import java.util.Optional;

public interface ContextPlanningPort {
    Optional<ContextSnapshot> load(ContextReadRequest request);
    RuntimeContextView toRuntimeView(
            ContextSnapshot snapshot,
            ContextReadDeclaration declaration,
            PlanningAuthorizationEvidence evidence);
}
