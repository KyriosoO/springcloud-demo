package com.dylan.agent.metadata.context.internal;

import com.dylan.agent.invocation.model.ConversationScope;
import com.dylan.agent.invocation.model.InvocationScope;
import com.dylan.agent.invocation.model.RunScope;
import com.dylan.agent.kernel.port.model.ApprovedContextWrite;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.Objects;

/**
 * Context payload AAD 的稳定绑定摘要与 scope 编解码；字段顺序必须与写入和读取保持一致。
 */
final class ContextBindingSupport {

    private ContextBindingSupport() {
    }

    static String bindingDigest(ContextRecordEntity entity) {
        return sha256Hex(canonical(
                entity.recordKey().owner().type(),
                entity.recordKey().owner().id(),
                scopeType(entity.recordKey().scope()),
                entity.recordKey().scope().scopeId(),
                entity.recordKey().contextType().name(),
                entity.sourceCapabilityId(),
                entity.sourceInvocationId(),
                Objects.toString(entity.sourceDomain(), ""),
                Long.toString(entity.recordVersion())));
    }

    static String bindingDigest(ApprovedContextWrite write) {
        return sha256Hex(canonical(
                write.recordKey().owner().type(),
                write.recordKey().owner().id(),
                scopeType(write.recordKey().scope()),
                write.recordKey().scope().scopeId(),
                write.recordKey().contextType().name(),
                write.sourceCapabilityId(),
                write.sourceInvocationId(),
                write.sourceDomain().orElse(""),
                Long.toString(write.expectedVersion().targetVersion())));
    }

    static String scopeType(InvocationScope scope) {
        if (scope instanceof ConversationScope) {
            return "CONVERSATION";
        }
        if (scope instanceof RunScope) {
            return "RUN";
        }
        throw new IllegalArgumentException("unsupported context scope type: "
                + scope.getClass().getName());
    }

    static InvocationScope scope(String scopeType, String scopeId) {
        return switch (scopeType) {
            case "CONVERSATION" -> new ConversationScope(scopeId);
            case "RUN" -> new RunScope(scopeId);
            default -> throw new IllegalArgumentException("unsupported scopeType: " + scopeType);
        };
    }

    static boolean sameScope(InvocationScope left, InvocationScope right) {
        return scopeType(left).equals(scopeType(right)) && left.scopeId().equals(right.scopeId());
    }

    private static String sha256Hex(String canonical) {
        try {
            byte[] digest = MessageDigest.getInstance("SHA-256")
                    .digest(canonical.getBytes(StandardCharsets.UTF_8));
            StringBuilder hex = new StringBuilder(digest.length * 2);
            for (byte b : digest) {
                hex.append(String.format("%02x", b));
            }
            return hex.toString();
        } catch (Exception ex) {
            throw new IllegalStateException("failed to compute context binding digest", ex);
        }
    }

    private static String canonical(String... fields) {
        StringBuilder builder = new StringBuilder();
        for (String field : fields) {
            String value = Objects.toString(field, "");
            builder.append(value.length()).append(':').append(value).append('|');
        }
        return builder.toString();
    }
}
