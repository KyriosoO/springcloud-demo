package com.dylan.baseline.agent.security.authorization.internal;

import com.dylan.baseline.agent.security.authorization.SubjectRef;
import java.time.Instant;

record AuthPermissionWireRequest(
        String requestId,
        SubjectRef subject,
        Instant requestedAt,
        Instant deadline) {
}
