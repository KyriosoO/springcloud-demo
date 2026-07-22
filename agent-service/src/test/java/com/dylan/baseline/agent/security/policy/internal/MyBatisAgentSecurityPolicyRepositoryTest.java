package com.dylan.baseline.agent.security.policy.internal;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.dylan.baseline.agent.security.policy.StoredAgentSecurityPolicy;
import com.dylan.baseline.agent.security.policy.admin.SecurityPolicyAdministrationRepository.ActivationResult;
import com.dylan.baseline.agent.security.policy.admin.SecurityPolicyAdministrationRepository.AuditUnavailableException;
import com.dylan.baseline.agent.security.policy.admin.SecurityPolicyAdministrationRepository.PreparedActivation;
import com.dylan.baseline.agent.security.policy.admin.SecurityPolicyAdministrationRepository.StoredPolicyVersion;
import com.dylan.baseline.agent.security.policy.admin.SecurityPolicyAdministrationRepository.WriteConflictException;
import java.time.Instant;
import org.junit.jupiter.api.Test;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.TransactionDefinition;
import org.springframework.transaction.TransactionStatus;
import org.springframework.transaction.support.SimpleTransactionStatus;
import org.springframework.transaction.support.TransactionTemplate;

class MyBatisAgentSecurityPolicyRepositoryTest {

    private static final Instant NOW = Instant.parse("2026-07-22T08:00:00Z");

    @Test
    void initialActivationCommitsVersionPointerAndAuditTogether() {
        AgentSecurityPolicyRecordMapper mapper = mock(AgentSecurityPolicyRecordMapper.class);
        RecordingTransactionManager transactions = new RecordingTransactionManager();
        when(mapper.insertVersion(any(), anyString(), anyString(), any())).thenReturn(1);
        when(mapper.insertInitialActive(anyString(), anyString(), any(), anyString())).thenReturn(1);
        when(mapper.insertActivationAudit(
                anyString(), any(), anyString(), anyString(), anyLong(), anyString(), anyString(),
                anyString(), anyString(), anyString(), anyString(), any())).thenReturn(1);
        MyBatisAgentSecurityPolicyRepository repository = repository(mapper, transactions);

        ActivationResult result = repository.activateAtomically(initialActivation());

        assertThat(result.policyEpoch()).isEqualTo(1);
        assertThat(transactions.commits).isEqualTo(1);
        assertThat(transactions.rollbacks).isZero();
        verify(mapper).insertVersion(any(), anyString(), anyString(), any());
        verify(mapper).insertInitialActive(anyString(), anyString(), any(), anyString());
        verify(mapper).insertActivationAudit(
                anyString(), any(), anyString(), anyString(), anyLong(), anyString(), anyString(),
                anyString(), anyString(), anyString(), anyString(), any());
    }

    @Test
    void auditFailureRollsBackTheTransactionAndDoesNotReportActivation() {
        AgentSecurityPolicyRecordMapper mapper = mock(AgentSecurityPolicyRecordMapper.class);
        RecordingTransactionManager transactions = new RecordingTransactionManager();
        when(mapper.insertVersion(any(), anyString(), anyString(), any())).thenReturn(1);
        when(mapper.insertInitialActive(anyString(), anyString(), any(), anyString())).thenReturn(1);
        when(mapper.insertActivationAudit(
                anyString(), any(), anyString(), anyString(), anyLong(), anyString(), anyString(),
                anyString(), anyString(), anyString(), anyString(), any()))
                .thenThrow(new DataIntegrityViolationException("audit unavailable"));
        MyBatisAgentSecurityPolicyRepository repository = repository(mapper, transactions);

        assertThatThrownBy(() -> repository.activateAtomically(initialActivation()))
                .isInstanceOf(AuditUnavailableException.class);
        assertThat(transactions.commits).isZero();
        assertThat(transactions.rollbacks).isEqualTo(1);
    }

    @Test
    void lockedPayloadDriftFailsBeforeAnyWrite() {
        AgentSecurityPolicyRecordMapper mapper = mock(AgentSecurityPolicyRecordMapper.class);
        RecordingTransactionManager transactions = new RecordingTransactionManager();
        when(mapper.selectActiveForUpdate()).thenReturn(new StoredAgentSecurityPolicy(
                "policy-v0", "agent-field-policy-v0.1", "{\"changed\":true}", "0".repeat(64), 2, 2));
        MyBatisAgentSecurityPolicyRepository repository = repository(mapper, transactions);
        PreparedActivation activation = new PreparedActivation(
                version(), true, "policy-v0", "agent-field-policy-v0.1", "{\"original\":true}",
                "0".repeat(64), 2, "approval-1", "e".repeat(64), "SERVICE", "a".repeat(64),
                "corr-1", NOW);

        assertThatThrownBy(() -> repository.activateAtomically(activation))
                .isInstanceOf(WriteConflictException.class);
        assertThat(transactions.rollbacks).isEqualTo(1);
        verify(mapper, never()).insertVersion(any(), anyString(), anyString(), any());
    }

    private static MyBatisAgentSecurityPolicyRepository repository(
            AgentSecurityPolicyRecordMapper mapper, RecordingTransactionManager transactions) {
        return new MyBatisAgentSecurityPolicyRepository(mapper, new TransactionTemplate(transactions));
    }

    private static PreparedActivation initialActivation() {
        return new PreparedActivation(
                version(), true, null, null, null, null, 0, "approval-1", "e".repeat(64),
                "SERVICE", "a".repeat(64), "corr-1", NOW);
    }

    private static StoredPolicyVersion version() {
        return new StoredPolicyVersion(
                "policy-v1", "agent-field-policy-v0.1", "{\"fieldPolicies\":{}}",
                "d".repeat(64), "INITIAL");
    }

    private static final class RecordingTransactionManager implements PlatformTransactionManager {
        private int commits;
        private int rollbacks;

        @Override
        public TransactionStatus getTransaction(TransactionDefinition definition) {
            return new SimpleTransactionStatus();
        }

        @Override
        public void commit(TransactionStatus status) {
            commits++;
        }

        @Override
        public void rollback(TransactionStatus status) {
            rollbacks++;
        }
    }
}
