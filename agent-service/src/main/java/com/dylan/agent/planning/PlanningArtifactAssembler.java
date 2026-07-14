package com.dylan.agent.planning;

import com.dylan.agent.api.contract.runtime.plan.AgentPlan;
import com.dylan.agent.kernel.registration.ResolvedRegistration;
import com.dylan.agent.metadata.authorization.model.AuthorizationSnapshot;
import com.dylan.agent.metadata.authorization.model.PlanningAuthorizationEvidence;
import com.dylan.agent.planning.model.PlanningCommand;

/** Capability-local server-origin planning binding seam；非目标 capability 必须保持 identity。 */
public interface PlanningArtifactAssembler {
    PreparedBinding prepare(PlanningCommand command, PlanningAuthorizationEvidence evidence,
                            ValidatedRouteDecision route, ResolvedRegistration registration);

    FrozenBinding freeze(PreparedBinding prepared, AuthorizationSnapshot authorizationSnapshot);

    AgentPlan assemble(AgentPlan runtimePlan, FrozenBinding frozen);

    interface PreparedBinding {}
    interface FrozenBinding {}

    record IdentityBinding() implements PreparedBinding {}
    record IdentityFrozenBinding() implements FrozenBinding {}

    static PlanningArtifactAssembler identity() {
        return new PlanningArtifactAssembler() {
            @Override public PreparedBinding prepare(PlanningCommand command, PlanningAuthorizationEvidence evidence,
                                                     ValidatedRouteDecision route, ResolvedRegistration registration) {
                return new IdentityBinding();
            }
            @Override public FrozenBinding freeze(PreparedBinding prepared, AuthorizationSnapshot authorizationSnapshot) {
                return new IdentityFrozenBinding();
            }
            @Override public AgentPlan assemble(AgentPlan runtimePlan, FrozenBinding frozen) { return runtimePlan; }
        };
    }
}
