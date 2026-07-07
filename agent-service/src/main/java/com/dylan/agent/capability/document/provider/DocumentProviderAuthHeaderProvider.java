package com.dylan.agent.capability.document.provider;

import com.dylan.common.security.ServiceTokenProvider;

import java.util.Objects;

/** 文档 provider 内部调用的服务 token 认证头生成器。 */
public final class DocumentProviderAuthHeaderProvider {

    private final ServiceTokenProvider serviceTokenProvider;

    public DocumentProviderAuthHeaderProvider(ServiceTokenProvider serviceTokenProvider) {
        this.serviceTokenProvider = Objects.requireNonNull(serviceTokenProvider, "serviceTokenProvider must not be null");
    }

    public String authorizationHeader() {
        String token = serviceTokenProvider.token();
        if (token == null || token.isBlank()) {
            throw new IllegalStateException("document provider service token is unavailable");
        }
        return "Bearer " + token.trim();
    }
}
