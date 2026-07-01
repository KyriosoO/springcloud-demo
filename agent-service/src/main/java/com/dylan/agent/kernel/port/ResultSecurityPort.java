package com.dylan.agent.kernel.port;

import com.dylan.agent.api.contract.common.ContractRef;
import com.dylan.agent.kernel.port.model.SecuredResult;
import com.dylan.agent.metadata.authorization.model.ExecutionScope;

public interface ResultSecurityPort {
    SecuredResult secure(Object candidate, ContractRef outputContract, ExecutionScope scope);
}
