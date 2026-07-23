package com.dylan.esquery.document.governance.emergency;

public record DocumentEmergencyRolloutBinding(
        String unitType, String unitKeyDigest, String expectedStateDigest,
        String targetStateDigest, String validationReportId) {
    public DocumentEmergencyRolloutBinding {
        if (!"INDEX_TARGET".equals(unitType)) throw new IllegalArgumentException("unitType must be INDEX_TARGET");
        digest(unitKeyDigest, "unitKeyDigest");
        digest(expectedStateDigest, "expectedStateDigest");
        digest(targetStateDigest, "targetStateDigest");
        if (validationReportId == null || !validationReportId.matches("[A-Za-z0-9._:-]{1,128}")) {
            throw new IllegalArgumentException("validationReportId must be a safe identifier");
        }
    }
    private static void digest(String value,String name){if(value==null||!value.matches("[0-9a-f]{64}"))throw new IllegalArgumentException(name+" must be SHA-256 hex");}
}
