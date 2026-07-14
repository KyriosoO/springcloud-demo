package com.dylan.agent.capability.document.security;

import com.dylan.agent.api.contract.common.ContractRef;
import com.dylan.agent.api.response.DocumentResultCandidateSecurityEvidence;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.HexFormat;
import java.util.List;

/** 对 Result sidecar 重算与 Handler 相同的 DCS-1。 */
public final class DocumentResultCandidateSetCanonicalizer {
    public String digest(List<DocumentResultCandidateSecurityEvidence> candidates,List<String> refs,ContractRef contract){
        try{MessageDigest md=MessageDigest.getInstance("SHA-256");update(md,"DCS-1");
            for(var c:List.copyOf(candidates)){for(String value:new String[]{c.candidateId(),c.documentId(),c.documentVersion(),c.chunkId(),
                    Integer.toString(c.chunkIndex()),c.protectedFilterDigest(),c.aclEvidenceDigest(),c.aclRef(),c.aclVersion(),
                    c.manifestDigest(),c.attestationDigest(),c.profileProjectionDigest(),c.resourceLimitDigest()})update(md,value);}
            for(String ref:List.copyOf(refs))update(md,ref);update(md,contract.namespace());update(md,contract.name());update(md,contract.version());
            return HexFormat.of().formatHex(md.digest());
        }catch(NoSuchAlgorithmException ex){throw new IllegalStateException("SHA-256 unavailable",ex);}
    }
    private static void update(MessageDigest md,String value){byte[] b=String.valueOf(value).getBytes(StandardCharsets.UTF_8);md.update(new byte[]{(byte)(b.length>>>24),(byte)(b.length>>>16),(byte)(b.length>>>8),(byte)b.length});md.update(b);}
}
