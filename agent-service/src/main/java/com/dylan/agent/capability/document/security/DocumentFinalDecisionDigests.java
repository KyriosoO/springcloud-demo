package com.dylan.agent.capability.document.security;

import com.dylan.agent.capability.document.acl.DocumentCurrentnessOutcome;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.time.Instant;
import java.util.HexFormat;

public final class DocumentFinalDecisionDigests {
    private DocumentFinalDecisionDigests() {}
    public static String digest(DocumentCurrentnessOutcome outcome,String invocationId,String operationId,
                         String permissionVersion,String candidateSetDigest,String authorizationBindingDigest,
                         String limitDigest,String aclDecisionVersion,String emergencyViewVersion,
                         Instant checkedAt,Instant validUntil,DocumentSecurityReasonCode reason){
        try{MessageDigest md=MessageDigest.getInstance("SHA-256");
            for(String value:new String[]{"DFD-1",outcome.name(),invocationId,operationId,permissionVersion,
                    candidateSetDigest,authorizationBindingDigest,limitDigest,String.valueOf(aclDecisionVersion),
                    String.valueOf(emergencyViewVersion),checkedAt.toString(),validUntil.toString(),reason.name()}){
                byte[] bytes=value.getBytes(StandardCharsets.UTF_8);md.update(new byte[]{(byte)(bytes.length>>>24),(byte)(bytes.length>>>16),(byte)(bytes.length>>>8),(byte)bytes.length});md.update(bytes);}
            return HexFormat.of().formatHex(md.digest());
        }catch(NoSuchAlgorithmException ex){throw new IllegalStateException("SHA-256 unavailable",ex);}
    }
}
