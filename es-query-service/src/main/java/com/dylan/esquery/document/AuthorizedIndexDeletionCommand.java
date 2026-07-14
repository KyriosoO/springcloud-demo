package com.dylan.esquery.document;

import com.dylan.esquery.api.model.DocumentCorpusKeyDto;

import java.time.Instant;

/** 07 retention/legal checks完成后签发的单目标删除命令。 */
public record AuthorizedIndexDeletionCommand(
        DocumentCorpusKeyDto corpusKey,
        String physicalIndex,
        String expectedManifestDigest,
        String authorityDigest,
        Instant deadline) {
    public AuthorizedIndexDeletionCommand {
        if (corpusKey == null || physicalIndex == null || !physicalIndex.startsWith("agent-doc-")
                || expectedManifestDigest == null || !expectedManifestDigest.matches("[0-9a-f]{64}")
                || authorityDigest == null || !authorityDigest.matches("[0-9a-f]{64}") || deadline == null) {
            throw new IllegalArgumentException("authorized index deletion command invalid");
        }
    }
}
