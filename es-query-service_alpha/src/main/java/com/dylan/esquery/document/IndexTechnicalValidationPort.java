package com.dylan.esquery.document;

import java.time.Instant;

public interface IndexTechnicalValidationPort {
    IndexTechnicalValidationEvidence validate(IndexBuildTargetHandle handle, DocumentPhysicalIndexManifest manifest, Instant deadline);
}
