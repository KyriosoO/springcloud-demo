package com.dylan.documentprovider;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;

/** 在 JSON 反序列化和业务校验前拒绝未知长度或超限的 provider 请求体。 */
@Component
final class DocumentProviderRequestSizeFilter extends OncePerRequestFilter {
    private static final String PROVIDER_PATH_PREFIX = "/internal/document-providers/";
    private final long maxRequestBytes;

    DocumentProviderRequestSizeFilter(DocumentProviderOperationProperties properties) {
        this.maxRequestBytes = properties.getMaxRequestBytes();
    }

    @Override
    protected boolean shouldNotFilter(HttpServletRequest request) {
        return !request.getRequestURI().startsWith(PROVIDER_PATH_PREFIX);
    }

    @Override
    protected void doFilterInternal(
            HttpServletRequest request,
            HttpServletResponse response,
            FilterChain filterChain) throws ServletException, IOException {
        long contentLength = request.getContentLengthLong();
        if (contentLength <= 0 || contentLength > maxRequestBytes) {
            response.sendError(HttpStatus.PAYLOAD_TOO_LARGE.value());
            return;
        }
        filterChain.doFilter(request, response);
    }
}
