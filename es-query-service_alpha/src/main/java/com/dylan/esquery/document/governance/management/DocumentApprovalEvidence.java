package com.dylan.esquery.document.governance.management;

import java.time.Instant;

public record DocumentApprovalEvidence(String evidenceRef,String approverSafeRef,Instant validUntil,String canonicalDigest) {}
