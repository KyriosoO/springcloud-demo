package com.dylan.baseline.agent.security.migration.control;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotEquals;

import org.junit.jupiter.api.Test;

class Open04001ExecutionBindingTest {

    @Test
    void derivesStableDigestsAndBindsKeyAndDatabaseEndpoint() {
        String approver = "a".repeat(64);
        assertEquals("905695627cc088330549b54b9606954dc9bb58a290d156f8b57b444119115d73",
                Open04001ExecutionBinding.configurationDigest("approval-key", "v1", approver, new byte[]{1, 2}));
        assertNotEquals(
                Open04001ExecutionBinding.configurationDigest("approval-key", "v1", approver, new byte[]{1, 2}),
                Open04001ExecutionBinding.configurationDigest("approval-key", "v1", approver, new byte[]{2, 1}));
        assertEquals("3fb1e9fa612179b9631de90a918bc3d8110f08e06df0a61a3e9ef433c54fef4a",
                Open04001ExecutionBinding.databaseRefDigest(
                        "jdbc:mysql://127.0.0.1:3306/springboot_db", "root"));
        assertNotEquals(
                "3fb1e9fa612179b9631de90a918bc3d8110f08e06df0a61a3e9ef433c54fef4a",
                Open04001ExecutionBinding.databaseRefDigest(
                        "jdbc:mysql://127.0.0.1:3307/springboot_db", "root"));
    }
}
