package com.dylan.agent.metadata.authorization;

import com.dylan.agent.invocation.model.ExecutionSubjectRef;
import com.dylan.agent.invocation.model.KernelErrorCode;
import com.dylan.agent.metadata.authorization.internal.AuthorizationSecurityConfiguration;
import com.dylan.agent.metadata.authorization.internal.UserPermissionBoundary;
import com.dylan.agent.metadata.authorization.model.UserPermission;
import com.dylan.agent.metadata.authorization.port.UserPermissionAuthorityException;
import com.dylan.agent.metadata.authorization.port.UserPermissionAuthorityFailure;
import com.dylan.agent.metadata.authorization.port.UserPermissionAuthorityPort;
import org.junit.jupiter.api.Test;

import java.time.Clock;
import java.time.Instant;
import java.time.ZoneOffset;
import java.util.List;
import java.util.Map;
import java.util.Set;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class UserPermissionBoundaryTest {

    private static final Clock CLOCK =
            Clock.fixed(Instant.parse("2026-07-01T00:00:00Z"), ZoneOffset.UTC);
    private static final ExecutionSubjectRef SUBJECT = new ExecutionSubjectRef("user", "u-1");

    @Test
    void resolvesAndDefensivelyCopiesAuthorityProjection() {
        UserPermissionBoundary boundary = new UserPermissionBoundary(
                (subject, deadline) -> permission(subject), CLOCK);

        UserPermission resolved = boundary.resolve(SUBJECT, CLOCK.instant().plusSeconds(10));

        assertThat(resolved.subject()).isEqualTo(SUBJECT);
        assertThat(resolved.allowedCapabilityIds()).containsExactly("query.search");
        assertThatThrownBy(() -> resolved.allowedCapabilityIds().add("other"))
                .isInstanceOf(UnsupportedOperationException.class);
    }

    @Test
    void mapsAuthorityFailureAndInvalidResponseFailClosed() {
        UserPermissionBoundary unavailable = new UserPermissionBoundary(
                throwing(UserPermissionAuthorityFailure.UNAVAILABLE), CLOCK);

        assertThatThrownBy(() -> unavailable.resolve(SUBJECT, CLOCK.instant().plusSeconds(10)))
                .isInstanceOf(UserPermissionBoundary.UserPermissionBoundaryException.class)
                .extracting("errorCode")
                .isEqualTo(KernelErrorCode.PERMISSION_UNAVAILABLE);

        UserPermissionBoundary mismatch = new UserPermissionBoundary(
                (subject, deadline) -> permission(new ExecutionSubjectRef("user", "other")), CLOCK);

        assertThatThrownBy(() -> mismatch.resolve(SUBJECT, CLOCK.instant().plusSeconds(10)))
                .isInstanceOf(UserPermissionBoundary.UserPermissionBoundaryException.class)
                .extracting("errorCode")
                .isEqualTo(KernelErrorCode.PERMISSION_UNAVAILABLE);
    }

    @Test
    void deadlineFailureUsesDeadlineCode() {
        UserPermissionBoundary boundary = new UserPermissionBoundary(
                (subject, deadline) -> permission(subject), CLOCK);

        assertThatThrownBy(() -> boundary.resolve(SUBJECT, CLOCK.instant()))
                .isInstanceOf(UserPermissionBoundary.UserPermissionBoundaryException.class)
                .extracting("errorCode")
                .isEqualTo(KernelErrorCode.DEADLINE_EXCEEDED);

        UserPermissionBoundary authorityDeadline = new UserPermissionBoundary(
                throwing(UserPermissionAuthorityFailure.DEADLINE_EXCEEDED), CLOCK);

        assertThatThrownBy(() -> authorityDeadline.resolve(SUBJECT, CLOCK.instant().plusSeconds(10)))
                .isInstanceOf(UserPermissionBoundary.UserPermissionBoundaryException.class)
                .extracting("errorCode")
                .isEqualTo(KernelErrorCode.DEADLINE_EXCEEDED);
    }

    @Test
    void configurationRequiresExactlyOneAuthorityPort() {
        AuthorizationSecurityConfiguration configuration = new AuthorizationSecurityConfiguration();
        UserPermissionAuthorityPort port = (subject, deadline) -> permission(subject);

        assertThat(configuration.userPermissionBoundary(List.of(port), CLOCK)).isNotNull();
        assertThatThrownBy(() -> configuration.userPermissionBoundary(List.of(), CLOCK))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("Exactly one");
        assertThatThrownBy(() -> configuration.userPermissionBoundary(List.of(port, port), CLOCK))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("Exactly one");
    }

    private static UserPermissionAuthorityPort throwing(UserPermissionAuthorityFailure failure) {
        return (subject, deadline) -> {
            throw new UserPermissionAuthorityException(failure, "diag-1", null);
        };
    }

    private static UserPermission permission(ExecutionSubjectRef subject) {
        return new UserPermission(
                subject,
                "evidence-1",
                "v1",
                Set.of("query.search"),
                Set.of("employee"),
                Map.of("employee", Set.of("name")),
                Map.of("employee", Set.of("name")),
                Map.of(),
                Map.of(),
                Set.of("QUERY"),
                Set.of("QUERY"),
                Map.of("department", "it"),
                CLOCK.instant());
    }
}
