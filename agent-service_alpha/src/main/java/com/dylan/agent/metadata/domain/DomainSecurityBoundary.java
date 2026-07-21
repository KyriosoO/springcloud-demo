package com.dylan.agent.metadata.domain;

import com.dylan.agent.kernel.port.DomainExecutionPort;
import com.dylan.agent.kernel.port.model.DomainBindingRequest;
import com.dylan.agent.kernel.port.model.DomainExecutionResolution;
import com.dylan.agent.metadata.domain.port.DomainMetadataPort;

import java.util.Objects;

/** 由 D04 DomainMetadataPort 支撑的 D02_03 execution boundary。 */
public final class DomainSecurityBoundary implements DomainExecutionPort {

    private final DomainMetadataPort domainMetadataPort;

    public DomainSecurityBoundary(DomainMetadataPort domainMetadataPort) {
        this.domainMetadataPort = Objects.requireNonNull(domainMetadataPort);
    }

    @Override
    public DomainExecutionResolution resolve(DomainBindingRequest request) {
        Objects.requireNonNull(request, "request must not be null");
        var registration = request.registration();
        var role = registration.registration().definition().adapterRole()
                .orElseThrow(() -> new IllegalStateException("domain registration requires adapterRole"));
        return domainMetadataPort.resolveExecution(
                role,
                request.selectedDomain(),
                request.executionScope(),
                request.expectedEvidence(),
                request.absoluteDeadline());
    }
}
