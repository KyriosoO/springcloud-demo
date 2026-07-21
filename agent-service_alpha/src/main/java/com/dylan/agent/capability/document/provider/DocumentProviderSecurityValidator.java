package com.dylan.agent.capability.document.provider;

import com.dylan.common.security.ServiceTokenProperties;
import org.springframework.beans.factory.InitializingBean;
import org.springframework.stereotype.Component;

/** Document Provider 调用链强制具备专用内部调用 scope。 */
@Component
public final class DocumentProviderSecurityValidator implements InitializingBean {
    public static final String PROVIDER_INVOKE_SCOPE = "agent.document.provider.invoke";
    private final ServiceTokenProperties serviceTokenProperties;

    public DocumentProviderSecurityValidator(ServiceTokenProperties serviceTokenProperties) {
        this.serviceTokenProperties = serviceTokenProperties;
    }

    @Override
    public void afterPropertiesSet() {
        if (serviceTokenProperties.getScopes() == null || serviceTokenProperties.getScopes().stream()
                .noneMatch(PROVIDER_INVOKE_SCOPE::equals)) {
            throw new IllegalStateException("common.security.service-token.scopes 必须包含 agent.document.provider.invoke。");
        }
    }
}
