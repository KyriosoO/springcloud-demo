package com.dylan.agent.metadata.context;

import com.dylan.agent.api.context.QueryCapabilityContextPayload;
import com.dylan.agent.api.contract.common.ContractRef;
import com.dylan.agent.api.contract.runtime.common.RuntimeContextType;
import com.dylan.agent.invocation.model.ContextOwnerRef;
import com.dylan.agent.invocation.model.ConversationScope;
import com.dylan.agent.invocation.model.InvocationHandle;
import com.dylan.agent.kernel.port.model.ContextApprovalRequest;
import com.dylan.agent.kernel.port.model.ExpectedContextVersion;
import com.dylan.agent.kernel.registration.ResolvedRegistration;
import com.dylan.agent.metadata.authorization.model.ExecutionScope;
import com.dylan.agent.metadata.context.model.ContextRecordKey;
import com.dylan.agent.metadata.context.model.ContextSnapshot;
import org.junit.jupiter.api.Test;

import java.time.Instant;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.mock;

class ContextSnapshotTest {

    @Test
    void snapshotCarriesRecordKeySourceEvidenceAndExpectedWriteVersion() {
        ContextSnapshot snapshot = snapshot(ExpectedContextVersion.version(3));

        assertThat(snapshot.recordKey().contextType()).isEqualTo(RuntimeContextType.QUERY);
        assertThat(snapshot.owner()).isEqualTo(new ContextOwnerRef("conversation", "conv-1"));
        assertThat(snapshot.sourceCapabilityId()).isEqualTo("query.search");
        assertThat(snapshot.sourceInvocationId()).isEqualTo("inv-previous");
        assertThat(snapshot.profileEvidenceRef()).isEqualTo("profile-v1");
        assertThat(snapshot.policyEvidenceRef()).isEqualTo("policy-v1");
        assertThat(snapshot.permissionEvidenceRef()).isEqualTo("permission-v1");
        assertThat(snapshot.expectedWriteVersion().targetVersion()).isEqualTo(4);
    }

    @Test
    void snapshotRejectsMismatchedExpectedVersionOrPayloadType() {
        assertThatThrownBy(() -> snapshot(ExpectedContextVersion.version(2)))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("expectedWriteVersion");

        assertThatThrownBy(() -> new ContextSnapshot(
                "ctx-1",
                "corr-1",
                new ContextRecordKey(
                        new ContextOwnerRef("conversation", "conv-1"),
                        new ConversationScope("conv-1"),
                        RuntimeContextType.AGGREGATE),
                "query.search",
                "inv-previous",
                "employee",
                contract(),
                contract(),
                3,
                Instant.parse("2026-07-01T00:10:00Z"),
                "profile-v1",
                "policy-v1",
                "permission-v1",
                null,
                ExpectedContextVersion.version(3),
                payload()))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("contextType");
    }

    @Test
    void approvalRequestIndexesConsumedSnapshotsByContextTypeAndRejectsDuplicates() {
        ContextSnapshot snapshot = snapshot(ExpectedContextVersion.version(3));

        ContextApprovalRequest request = new ContextApprovalRequest(
                mock(InvocationHandle.class),
                mock(ResolvedRegistration.class),
                mock(ExecutionScope.class),
                List.of(snapshot),
                Instant.parse("2026-07-01T00:00:00Z"));

        assertThat(request.consumedSnapshot(RuntimeContextType.QUERY)).containsSame(snapshot);
        assertThat(request.consumedSnapshotsByType()).containsOnlyKeys(RuntimeContextType.QUERY);
        assertThatThrownBy(() -> new ContextApprovalRequest(
                mock(InvocationHandle.class),
                mock(ResolvedRegistration.class),
                mock(ExecutionScope.class),
                List.of(snapshot, snapshot),
                Instant.parse("2026-07-01T00:00:00Z")))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("duplicate consumed contextType");
    }

    private ContextSnapshot snapshot(ExpectedContextVersion expectedVersion) {
        return new ContextSnapshot(
                "ctx-1",
                "corr-1",
                new ContextRecordKey(
                        new ContextOwnerRef("conversation", "conv-1"),
                        new ConversationScope("conv-1"),
                        RuntimeContextType.QUERY),
                "query.search",
                "inv-previous",
                "employee",
                contract(),
                contract(),
                3,
                Instant.parse("2026-07-01T00:10:00Z"),
                "profile-v1",
                "policy-v1",
                "permission-v1",
                null,
                expectedVersion,
                payload());
    }

    private QueryCapabilityContextPayload payload() {
        return new QueryCapabilityContextPayload(List.of(), List.of("name"), 1, 20);
    }

    private ContractRef contract() {
        return new ContractRef("agent.test", "QueryCapabilityContextPayload", "v1");
    }
}
