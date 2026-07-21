package com.dylan.agent.capability.document.profile;

import com.dylan.agent.shared.ref.AgentProfileRef;

import java.util.HashSet;
import java.util.List;
import java.util.Objects;
import java.util.Set;

/** exact AgentProfile 拥有的不可变文档 Profile 子资产。 */
public record DocumentProfileSet(
        AgentProfileRef ownerProfileRef,
        String documentProfileVersion,
        List<DocumentRetrievalProfile> profiles) {
    public DocumentProfileSet {
        Objects.requireNonNull(ownerProfileRef);
        if (ownerProfileRef.expectedVersion().isEmpty()) {
            throw new IllegalArgumentException("document profile owner must be exact");
        }
        if (documentProfileVersion == null || !documentProfileVersion.matches("dp1-[0-9a-f]{64}")) {
            throw new IllegalArgumentException("documentProfileVersion must be a full DPROFILE-1 SHA-256 version");
        }
        profiles = List.copyOf(Objects.requireNonNull(profiles));
        if (profiles.isEmpty()) throw new IllegalArgumentException("document profiles must not be empty");
        if (profiles.size() > 128) throw new IllegalArgumentException("too many document profiles");
        Set<String> keys = new HashSet<>();
        Set<String> domains = new HashSet<>();
        for (DocumentRetrievalProfile profile : profiles) {
            if (!keys.add(profile.domain() + "\u001f" + profile.profileName())) {
                throw new IllegalArgumentException("duplicate document domain/profileName");
            }
            domains.add(profile.domain());
        }
        for (String domain : domains) {
            long defaults = profiles.stream().filter(profile -> profile.domain().equals(domain) && profile.defaultProfile()).count();
            if (defaults != 1) throw new IllegalArgumentException("each document domain must have exactly one default profile");
            if (profiles.stream().filter(profile -> profile.domain().equals(domain)).count() > 32) {
                throw new IllegalArgumentException("too many document profiles for domain");
            }
        }
    }
}
