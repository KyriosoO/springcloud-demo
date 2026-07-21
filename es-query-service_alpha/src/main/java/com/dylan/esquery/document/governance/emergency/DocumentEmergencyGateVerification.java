package com.dylan.esquery.document.governance.emergency;

public record DocumentEmergencyGateVerification(DocumentEmergencyGateVerificationCode code,String diagnosticId) {
    public boolean allowsRollout(){return code==DocumentEmergencyGateVerificationCode.VERIFIED;}
}
