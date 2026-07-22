package com.dylan.baseline.agent.security.migration.control;

import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.nio.file.Files;
import java.nio.file.Path;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

class Open04001RepositoryRevisionTest {

    @TempDir
    Path root;

    @Test
    void acceptsExactCleanCommitAndRejectsTrackedOrUntrackedSecurityDrift() throws Exception {
        git("init");
        git("config", "user.email", "open-04-001@example.invalid");
        git("config", "user.name", "OPEN-04-001 Test");
        Path source = root.resolve("scripts/security/verifier.py");
        Files.createDirectories(source.getParent());
        Files.writeString(source, "secure\n");
        git("add", "scripts/security/verifier.py");
        git("commit", "-m", "baseline");
        String revision = git("rev-parse", "HEAD").strip();

        Open04001RepositoryRevision.verify(root, revision);

        Files.writeString(source, "drifted\n");
        assertThatThrownBy(() -> Open04001RepositoryRevision.verify(root, revision))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("differs");
        Files.writeString(source, "secure\n");
        Files.writeString(root.resolve("scripts/security/untracked.py"), "untracked\n");
        assertThatThrownBy(() -> Open04001RepositoryRevision.verify(root, revision))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("not clean");
    }

    private String git(String... arguments) throws Exception {
        String[] command = new String[arguments.length + 3];
        command[0] = "git";
        command[1] = "-C";
        command[2] = root.toString();
        System.arraycopy(arguments, 0, command, 3, arguments.length);
        Process process = new ProcessBuilder(command).redirectErrorStream(true).start();
        String output = new String(process.getInputStream().readAllBytes(), java.nio.charset.StandardCharsets.UTF_8);
        if (process.waitFor() != 0) {
            throw new IllegalStateException(output);
        }
        return output;
    }
}
