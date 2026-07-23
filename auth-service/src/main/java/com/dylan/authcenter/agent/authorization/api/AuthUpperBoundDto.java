package com.dylan.authcenter.agent.authorization.api;

import java.util.Map;
import java.util.Set;

public record AuthUpperBoundDto(
		Set<String> permissionCodes,
		Set<String> allowedCapabilityIds,
		Set<String> allowedDomains,
		Map<String, Set<String>> filterableFields,
		Map<String, Set<String>> displayableFields,
		Map<String, Set<String>> allowedOperators,
		Map<String, Set<String>> allowedFunctions,
		String authEvidenceVersion) {
}
