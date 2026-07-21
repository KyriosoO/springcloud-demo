package com.dylan.agent.capability.document.governance.provider;
import com.dylan.agent.adapter.api.document.provider.*;
import com.dylan.agent.adapter.api.operation.CapabilityOperationType;
import com.dylan.agent.adapter.api.operation.ProviderSafeIdentity;
import org.springframework.jdbc.core.JdbcTemplate;
import java.time.*;
import java.util.Optional;

/** 07 Provider activation current authority 的本地读取实现。 */
public final class JdbcDocumentProviderActivationReadView implements DocumentProviderActivationReadView {
    private final JdbcTemplate jdbc; private final Clock clock; private final DocumentProviderCanonicalizer canonicalizer;
    public JdbcDocumentProviderActivationReadView(JdbcTemplate jdbc,Clock clock,DocumentProviderCanonicalizer canonicalizer){this.jdbc=jdbc;this.clock=clock;this.canonicalizer=canonicalizer;}
    @Override public DocumentProviderActivationSnapshot requireCurrent(CapabilityOperationType type){var rows=jdbc.query("SELECT state,provider_safe_identity,provider_model_identity,adapter_service_identity_ref,adapter_deployment_ref,vendor_contract_version,template_model_digest,provider_binding_digest,wire_contract_version,rollout_version,valid_until,snapshot_digest FROM document_provider_activation WHERE operation_type=?",(rs,i)->{DocumentProviderActivationState state=DocumentProviderActivationState.valueOf(rs.getString(1));DocumentProviderBindingReference binding=state==DocumentProviderActivationState.ACTIVE?new DocumentProviderBindingReference(type,new ProviderSafeIdentity(rs.getString(2),Optional.ofNullable(rs.getString(3))),rs.getString(4),rs.getString(5),rs.getString(6),rs.getString(7),rs.getString(8)):null;return new DocumentProviderActivationSnapshot(type,state,Optional.ofNullable(binding),rs.getString(9),rs.getString(10),rs.getTimestamp(11).toInstant(),rs.getString(12));},type.value());if(rows.size()!=1)throw new IllegalStateException("provider activation unavailable");DocumentProviderActivationSnapshot snapshot=rows.getFirst();if(!clock.instant().isBefore(snapshot.validUntil())||snapshot.expectedProvider().filter(value->!value.canonicalDigest().equals(canonicalizer.providerBindingDigest(value))).isPresent()||!snapshot.canonicalDigest().equals(canonicalizer.activationSnapshotDigest(snapshot)))throw new IllegalStateException("provider activation stale or invalid");return snapshot;}
}
