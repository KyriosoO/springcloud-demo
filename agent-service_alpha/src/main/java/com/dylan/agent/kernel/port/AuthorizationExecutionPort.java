package com.dylan.agent.kernel.port;

import com.dylan.agent.invocation.model.InvocationHandle;
import com.dylan.agent.metadata.authorization.model.AuthorizationSnapshot;
import com.dylan.agent.metadata.authorization.model.ExecutionScope;

public interface AuthorizationExecutionPort {
    ExecutionScope recheck(AuthorizationSnapshot snapshot, InvocationHandle handle);
}
