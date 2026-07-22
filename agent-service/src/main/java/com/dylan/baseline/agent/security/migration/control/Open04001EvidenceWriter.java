package com.dylan.baseline.agent.security.migration.control;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;

/** 受控证据只允许同目录临时文件原子发布，既有证据不得覆盖。 */
final class Open04001EvidenceWriter {

    private Open04001EvidenceWriter() {
    }

    static void writeNew(Path target, String content) throws IOException {
        Path absolute = target.toAbsolutePath().normalize();
        Path parent = absolute.getParent();
        if (parent == null || !Files.isDirectory(parent)) {
            throw new IOException("evidence output parent directory does not exist");
        }
        if (Files.exists(absolute)) {
            throw new IOException("evidence output already exists");
        }
        Path temporary = Files.createTempFile(parent, ".open-04-001-", ".tmp");
        try {
            Files.writeString(temporary, content, StandardCharsets.UTF_8,
                    StandardOpenOption.TRUNCATE_EXISTING, StandardOpenOption.WRITE);
            Files.createLink(absolute, temporary);
        } finally {
            Files.deleteIfExists(temporary);
        }
    }
}
