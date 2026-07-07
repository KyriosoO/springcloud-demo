package com.dylan.agent.capability.document.provider;

import com.dylan.agent.config.AgentProperties;
import com.dylan.common.security.ServiceTokenProperties;
import org.springframework.beans.factory.InitializingBean;
import org.springframework.stereotype.Component;

import java.util.List;
import java.util.Objects;

/** 文档 provider 启用时的服务 token scope 门禁。 */
@Component
public final class DocumentProviderSecurityValidator implements InitializingBean {

    public static final String PROVIDER_INVOKE_SCOPE = "agent.document.provider.invoke";

    private final AgentProperties agentProperties;
    private final ServiceTokenProperties serviceTokenProperties;

    public DocumentProviderSecurityValidator(
            AgentProperties agentProperties,
            ServiceTokenProperties serviceTokenProperties) {
        this.agentProperties = Objects.requireNonNull(agentProperties, "agentProperties must not be null");
        this.serviceTokenProperties = Objects.requireNonNull(serviceTokenProperties, "serviceTokenProperties must not be null");
    }

    @Override
    public void afterPropertiesSet() {
        var document = agentProperties.getDocument();
        boolean providerEnabled = document.getEmbedding().isEnabled() || document.getGeneration().isEnabled();
        if (!providerEnabled) {
            return;
        }
        List<String> scopes = serviceTokenProperties.getScopes();
        boolean allowed = scopes != null && scopes.stream()
                .filter(Objects::nonNull)
                .map(String::trim)
                .anyMatch(PROVIDER_INVOKE_SCOPE::equals);
        if (!allowed) {
            throw new IllegalStateException("common.security.service-token.scopes 必须包含 agent.document.provider.invoke。");
        }
    }
}
