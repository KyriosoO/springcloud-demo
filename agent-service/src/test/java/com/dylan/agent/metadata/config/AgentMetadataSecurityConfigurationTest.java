package com.dylan.agent.metadata.config;

import com.dylan.agent.kernel.definition.ContractRegistry;
import com.dylan.agent.kernel.core.ExecutionCore;
import com.dylan.agent.kernel.config.CapabilityKernelConfiguration;
import com.dylan.agent.kernel.port.AuthorizationExecutionPort;
import com.dylan.agent.kernel.port.ContextApprovalPort;
import com.dylan.agent.kernel.port.ContextExecutionPort;
import com.dylan.agent.kernel.port.DomainExecutionPort;
import com.dylan.agent.kernel.port.ResultSecurityPort;
import com.dylan.agent.kernel.registration.CapabilityRegistrationValidator;
import com.dylan.agent.lifecycle.FinalizationTxService;
import com.dylan.agent.lifecycle.CheckpointTxService;
import com.dylan.agent.lifecycle.StartTxService;
import com.dylan.agent.invocation.model.ConversationScope;
import com.dylan.agent.kernel.port.model.ExpectedContextVersion;
import com.dylan.agent.capability.querypreview.QueryPreviewCapabilityConfiguration;
import com.dylan.agent.capability.querypreview.QueryPreviewCapabilityHandler;
import com.dylan.agent.capability.querypreview.QueryPreviewPlanValidator;
import com.dylan.agent.metadata.authorization.internal.AuthorizationSecurityConfiguration;
import com.dylan.agent.metadata.authorization.port.AuthorizationPlanningPort;
import com.dylan.agent.metadata.crypto.internal.PayloadJsonCodec;
import com.dylan.agent.metadata.authorization.port.UserPermissionAuthorityPort;
import com.dylan.agent.metadata.context.internal.ContextRecordEntity;
import com.dylan.agent.metadata.context.internal.ContextRepository;
import com.dylan.agent.metadata.context.internal.ContextSecurityConfiguration;
import com.dylan.agent.metadata.domain.internal.DomainMetadataConfiguration;
import com.dylan.agent.metadata.domain.port.DomainMetadataPort;
import com.dylan.agent.metadata.policy.internal.AgentPolicyConfiguration;
import com.dylan.agent.metadata.profile.internal.AgentProfileRegistry;
import com.dylan.agent.metadata.result.AggregateResultSecurityProjector;
import com.dylan.agent.metadata.result.QueryResultSecurityProjector;
import com.dylan.agent.metadata.result.ResultSecurityProjectorRegistry;
import com.dylan.agent.metadata.result.QueryPreviewResultSecurityProjector;
import com.dylan.agent.metadata.result.ResultValueMaskingSupport;
import com.dylan.agent.mask.AddressFieldMasker;
import com.dylan.agent.mask.EmailFieldMasker;
import com.dylan.agent.mask.FieldMaskerRegistry;
import com.dylan.agent.mask.IdCardFieldMasker;
import com.dylan.agent.mask.MobileFieldMasker;
import com.dylan.agent.mask.NoneFieldMasker;
import com.dylan.agent.testsupport.DomainMetadataTestSupport;
import com.dylan.agent.testsupport.KernelTestSupport;
import com.dylan.common.security.JwtConfig;
import org.junit.jupiter.api.Test;
import org.springframework.boot.autoconfigure.jackson.JacksonAutoConfiguration;
import org.springframework.boot.test.context.runner.ApplicationContextRunner;

import java.time.Clock;
import java.time.Instant;
import java.time.ZoneOffset;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

class AgentMetadataSecurityConfigurationTest {

    private final ApplicationContextRunner contextRunner = new ApplicationContextRunner()
            .withUserConfiguration(
                    JacksonAutoConfiguration.class,
                    JwtConfig.class,
                    AuthorizationSecurityConfiguration.class,
                    DomainMetadataConfiguration.class,
                    AgentMetadataSecurityConfiguration.class,
                    ContextSecurityConfiguration.class,
                    CapabilityKernelConfiguration.class)
            .withBean(com.dylan.agent.config.AgentProperties.class, DomainMetadataTestSupport::agentProperties)
            .withBean("agent.domain-metadata-com.dylan.agent.metadata.domain.internal.DomainMetadataProperties",
                    com.dylan.agent.metadata.domain.internal.DomainMetadataProperties.class,
                    DomainMetadataTestSupport::properties)
            .withPropertyValues(
                    "common.security.secrets.allow-config-values=true",
                    "common.security.secrets.source-order[0]=config",
                    "common.security.secrets.jwt.active-key-id=ACTIVE",
                    "common.security.secrets.jwt.keys.ACTIVE.value=AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=",
                    "common.security.secrets.agent-payload.active-key-id=ACTIVE",
                    "common.security.secrets.agent-payload.keys.ACTIVE.value=AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=",
                    "agent.document-profiles.owner-agent-id=agent-default",
                    "agent.document-profiles.owner-profile-version=profile-v1",
                    "agent.document-profiles.policy-version=policy-v1",
                    "agent.document-profiles.definitions[0].profile-name=employee-document-v1",
                    "agent.document-profiles.definitions[0].domain=employee",
                    "agent.document-profiles.definitions[0].default-profile=true",
                    "agent.document-profiles.definitions[0].allowed-material-types[0]=employee",
                    "agent.document-profiles.definitions[0].allowed-operations[0]=SEARCH",
                    "agent.document-profiles.definitions[0].allowed-operations[1]=ANSWER",
                    "agent.document-profiles.definitions[0].allowed-operations[2]=SUMMARIZE",
                    "agent.document-profiles.definitions[0].allowed-channels[0]=BM25",
                    "agent.document-profiles.definitions[0].required-channels[0]=BM25",
                    "agent.document-profiles.definitions[0].generation-policy.SEARCH=DISABLED",
                    "agent.document-profiles.definitions[0].generation-policy.ANSWER=OPTIONAL",
                    "agent.document-profiles.definitions[0].generation-policy.SUMMARIZE=OPTIONAL",
                    "agent.document-profiles.policy[0].domain=employee",
                    "agent.document-profiles.policy[0].allowed-profile-names[0]=employee-document-v1",
                    "agent.document-profiles.policy[0].allowed-channels[0]=BM25",
                    "agent.document-profiles.policy[0].allowed-operations[0]=SEARCH",
                    "agent.document-profiles.policy[0].allowed-operations[1]=ANSWER",
                    "agent.document-profiles.policy[0].allowed-operations[2]=SUMMARIZE")
            .withBean(Clock.class, () -> Clock.fixed(DomainMetadataTestSupport.TEST_CLOCK.instant(), ZoneOffset.UTC))
            .withBean("employeeAgentAdapter", DomainMetadataTestSupport.QueryableAggregatableAdapter.class,
                    DomainMetadataTestSupport.QueryableAggregatableAdapter::new)
            .withBean("transactionAgentAdapter", DomainMetadataTestSupport.QueryableAggregatableAdapter.class,
                    DomainMetadataTestSupport.QueryableAggregatableAdapter::new)
            .withBean(FieldMaskerRegistry.class, () -> new FieldMaskerRegistry(List.of(
                    new NoneFieldMasker(),
                    new IdCardFieldMasker(),
                    new MobileFieldMasker(),
                    new EmailFieldMasker(),
                    new AddressFieldMasker())))
            .withBean(UserPermissionAuthorityPort.class,
                    () -> (subject, deadline) -> com.dylan.agent.metadata.MetadataTestSupport.permission(subject))
            .withBean(com.dylan.common.security.ServiceTokenProvider.class,
                    () -> org.mockito.Mockito.mock(com.dylan.common.security.ServiceTokenProvider.class))
            .withBean(ContextRepository.class, NoopContextRepository::new)
            .withBean(CapabilityRegistrationValidator.class, CapabilityRegistrationValidator::new)
            .withBean("querySearchRegistration",
                    com.dylan.agent.kernel.registration.CapabilityRegistration.class,
                    () -> KernelTestSupport.resolvedQueryRegistration().registration())
            .withBean("queryPreviewRegistration",
                    com.dylan.agent.kernel.registration.CapabilityRegistration.class,
                    () -> new QueryPreviewCapabilityConfiguration().queryPreviewRegistration(
                            org.mockito.Mockito.mock(QueryPreviewPlanValidator.class),
                            org.mockito.Mockito.mock(QueryPreviewCapabilityHandler.class)))
            .withBean(StartTxService.class, () -> org.mockito.Mockito.mock(StartTxService.class))
            .withBean(CheckpointTxService.class, () -> org.mockito.Mockito.mock(CheckpointTxService.class))
            .withBean(FinalizationTxService.class, () -> org.mockito.Mockito.mock(FinalizationTxService.class));

    @Test
    void wiresExecutionSecurityPorts() {
        contextRunner.run(context -> {
            assertThat(context).hasSingleBean(AgentMetadataBootstrap.class);
            assertThat(context).hasSingleBean(AgentMetadataStore.class);
            assertThat(context).hasSingleBean(AgentProfileRegistry.class);
            assertThat(context).hasSingleBean(AgentPolicyConfiguration.class);
            assertThat(context).hasSingleBean(PayloadJsonCodec.class);
            assertThat(context).hasSingleBean(ResultSecurityProjectorRegistry.class);
            assertThat(context).hasSingleBean(ResultValueMaskingSupport.class);
            assertThat(context).hasSingleBean(QueryResultSecurityProjector.class);
            assertThat(context).hasSingleBean(QueryPreviewResultSecurityProjector.class);
            assertThat(context).hasSingleBean(AggregateResultSecurityProjector.class);
            assertThat(context).hasSingleBean(ResultSecurityPort.class);
            assertThat(context).hasSingleBean(DomainMetadataPort.class);
            assertThat(context).hasSingleBean(DomainExecutionPort.class);
            assertThat(context).hasSingleBean(AuthorizationPlanningPort.class);
            assertThat(context).hasSingleBean(AuthorizationExecutionPort.class);
            assertThat(context).hasSingleBean(ContextExecutionPort.class);
            assertThat(context).hasSingleBean(ContextApprovalPort.class);
            assertThat(context).hasSingleBean(ExecutionCore.class);
        });
    }

    private static final class NoopContextRepository implements ContextRepository {
        @Override
        public void upsertApproved(ContextRecordEntity record, ExpectedContextVersion expectedVersion) {
        }

        @Override
        public void markConversationUnreadable(ConversationScope scope, Instant now) {
        }

        @Override
        public int deleteExpired(Instant cutoff, int limit) {
            return 0;
        }
    }
}
