package com.dylan.agent.lifecycle;

import com.dylan.agent.application.StartChatCommand;
import com.dylan.agent.invocation.model.CancellationToken;
import com.dylan.agent.invocation.model.InvocationHandle;
import com.dylan.agent.kernel.core.ExecutionCommand;
import com.dylan.agent.kernel.core.ExecutionCore;
import com.dylan.agent.kernel.core.ExecutionFailure;
import com.dylan.agent.kernel.core.ExecutionSuccess;
import com.dylan.agent.lifecycle.model.CheckpointResult;
import com.dylan.agent.lifecycle.model.FinalizedInvocationResult;
import com.dylan.agent.planning.model.ExecutablePlanningResult;
import com.dylan.agent.planning.model.PlanningCancellation;
import com.dylan.agent.planning.model.PlanningFailure;
import com.dylan.agent.planning.model.ResolvedClarification;
import org.springframework.stereotype.Service;

import java.util.Objects;

/**
 * D03 生命周期协调器。
 *
 * <p>公开方法有意不持有事务。启动、检查点和终结都委托给短事务服务。</p>
 */
@Service
public class ExecutionLifecycleService {

    private final StartTxService startTxService;
    private final CheckpointTxService checkpointTxService;
    private final FinalizationTxService finalizationTxService;
    private final ExecutionCore executionCore;

    public ExecutionLifecycleService(StartTxService startTxService,
                                     CheckpointTxService checkpointTxService,
                                     FinalizationTxService finalizationTxService,
                                     ExecutionCore executionCore) {
        this.startTxService = Objects.requireNonNull(startTxService);
        this.checkpointTxService = Objects.requireNonNull(checkpointTxService);
        this.finalizationTxService = Objects.requireNonNull(finalizationTxService);
        this.executionCore = Objects.requireNonNull(executionCore);
    }

    public InvocationHandle startChat(StartChatCommand command) {
        return startTxService.createOrVerify(command).handle();
    }

    public CheckpointResult checkpoint(InvocationHandle handle, ExecutablePlanningResult result) {
        return checkpointTxService.write(handle, result);
    }

    public FinalizedInvocationResult executeAndFinalize(
            InvocationHandle handle,
            ExecutablePlanningResult result,
            CancellationToken token) {
        CheckpointResult checkpoint = checkpoint(handle, result);
        var outcome = executionCore.execute(new ExecutionCommand(handle, result, token));
        if (outcome instanceof ExecutionSuccess success) {
            return finalizationTxService.commitSuccess(handle, checkpoint, success);
        }
        if (outcome instanceof ExecutionFailure failure) {
            if (failure.cancelled()) {
                return finalizationTxService.commitExecutionCancelled(handle, checkpoint, failure);
            }
            return finalizationTxService.commitExecutionFailure(handle, checkpoint, failure);
        }
        throw new IllegalStateException("unknown execution outcome: " + outcome.getClass().getName());
    }

    public FinalizedInvocationResult finalizeClarification(
            InvocationHandle handle,
            ResolvedClarification clarification) {
        return finalizationTxService.commitClarification(handle, clarification);
    }

    public FinalizedInvocationResult finalizePlanningFailure(
            InvocationHandle handle,
            PlanningFailure failure) {
        return finalizationTxService.commitPlanningFailure(handle, failure);
    }

    public FinalizedInvocationResult finalizeCancelled(
            InvocationHandle handle,
            PlanningCancellation cancellation) {
        return finalizationTxService.commitPlanningCancellation(handle, cancellation);
    }
}
