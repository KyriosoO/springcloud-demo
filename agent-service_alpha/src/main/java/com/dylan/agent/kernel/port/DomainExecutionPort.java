package com.dylan.agent.kernel.port;

import com.dylan.agent.kernel.port.model.DomainBindingRequest;
import com.dylan.agent.kernel.port.model.DomainExecutionResolution;

public interface DomainExecutionPort {
    DomainExecutionResolution resolve(DomainBindingRequest request);
}
