package com.dylan.agent.kernel.port;

import com.dylan.agent.kernel.port.model.ApprovedContextWrite;
import com.dylan.agent.kernel.port.model.ContextApprovalRequest;
import com.dylan.agent.metadata.context.model.ContextWriteCandidate;

import java.util.List;

public interface ContextApprovalPort {
    List<ApprovedContextWrite> approve(List<ContextWriteCandidate> candidates,
                                       ContextApprovalRequest request);
}
