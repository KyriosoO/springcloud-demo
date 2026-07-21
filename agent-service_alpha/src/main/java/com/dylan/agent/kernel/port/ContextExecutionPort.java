package com.dylan.agent.kernel.port;

import com.dylan.agent.invocation.model.InvocationHandle;
import com.dylan.agent.kernel.registration.ResolvedRegistration;
import com.dylan.agent.metadata.authorization.model.ExecutionScope;
import com.dylan.agent.metadata.context.model.ContextSnapshot;

import java.util.List;

public interface ContextExecutionPort {
    void revalidateAll(List<ContextSnapshot> snapshots,
                       InvocationHandle handle,
                       ResolvedRegistration registration,
                       ExecutionScope scope);
}
