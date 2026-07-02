package com.dylan.agent.metadata.result;

import com.dylan.agent.api.contract.common.ContractRef;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;

/** Resolves one projector by output ContractRef; no capability/domain routing. */
public final class ResultSecurityProjectorRegistry {

    private final Map<ContractRef, ResultSecurityProjector<?>> projectors;

    public ResultSecurityProjectorRegistry(List<ResultSecurityProjector<?>> projectors) {
        Map<ContractRef, ResultSecurityProjector<?>> map = new LinkedHashMap<>();
        for (ResultSecurityProjector<?> projector : List.copyOf(projectors == null ? List.of() : projectors)) {
            ResultSecurityProjector<?> previous = map.putIfAbsent(projector.supports(), projector);
            if (previous != null) {
                throw new IllegalStateException("duplicate ResultSecurityProjector for " + projector.supports());
            }
        }
        this.projectors = Map.copyOf(map);
    }

    public ResultSecurityProjector<?> require(ContractRef outputContract) {
        ResultSecurityProjector<?> projector = projectors.get(Objects.requireNonNull(outputContract));
        if (projector == null) {
            throw new IllegalStateException("missing ResultSecurityProjector for " + outputContract);
        }
        return projector;
    }
}
