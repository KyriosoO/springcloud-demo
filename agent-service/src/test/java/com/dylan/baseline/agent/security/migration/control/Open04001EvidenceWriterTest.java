package com.dylan.baseline.agent.security.migration.control;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

class Open04001EvidenceWriterTest {

    @TempDir
    Path directory;

    @Test
    void publishesOnceAndNeverOverwritesExistingEvidence() throws Exception {
        Path target = directory.resolve("evidence.json");
        Open04001EvidenceWriter.writeNew(target, "first\n");
        assertThat(Files.readString(target)).isEqualTo("first\n");
        try (var files = Files.list(directory)) {
            assertThat(files.map(Path::getFileName).map(Path::toString).toList())
                    .containsExactly("evidence.json");
        }
        assertThatThrownBy(() -> Open04001EvidenceWriter.writeNew(target, "second\n"))
                .isInstanceOf(IOException.class)
                .hasMessageContaining("already exists");
        assertThat(Files.readString(target)).isEqualTo("first\n");
    }
}
