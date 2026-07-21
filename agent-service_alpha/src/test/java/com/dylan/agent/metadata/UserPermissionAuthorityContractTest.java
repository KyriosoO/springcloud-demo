package com.dylan.agent.metadata;

import static org.assertj.core.api.Assertions.assertThat;

import java.time.Clock;
import java.time.ZoneOffset;

import org.junit.jupiter.api.Test;

import com.dylan.agent.invocation.model.ExecutionSubjectRef;
import com.dylan.agent.metadata.authorization.internal.UserPermissionBoundary;

class UserPermissionAuthorityContractTest {
    @Test
    void authorityProjectionKeepsStableSubjectAndEvidence() {
        ExecutionSubjectRef subject = new ExecutionSubjectRef("user", "u-1");
        UserPermissionBoundary boundary = new UserPermissionBoundary(
                (s, deadline) -> MetadataTestSupport.permission(s),
                Clock.fixed(MetadataTestSupport.NOW, ZoneOffset.UTC));

        var permission = boundary.resolve(subject, MetadataTestSupport.NOW.plusSeconds(30));

        assertThat(permission.subject()).isEqualTo(subject);
        assertThat(permission.evidenceId()).isEqualTo("perm-evidence");
    }
}
