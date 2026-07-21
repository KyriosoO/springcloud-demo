package com.dylan.esquery.document.governance.emergency;

import com.dylan.common.security.IntegrityVerificationKeyProvider;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

import java.time.Duration;

@Configuration(proxyBeanMethods = false)
public class DocumentEmergencyGateVerificationConfiguration {
    @Bean
    DocumentEmergencyGateEvidenceVerifier documentEmergencyGateEvidenceVerifier(
            ObjectProvider<IntegrityVerificationKeyProvider> verificationKeys) {
        IntegrityVerificationKeyProvider failClosed = ref -> {
            throw new IllegalStateException("document governance verification key is unavailable");
        };
        return new DefaultDocumentEmergencyGateEvidenceVerifier(
                verificationKeys.getIfAvailable(() -> failClosed), Duration.ofSeconds(1));
    }
}
