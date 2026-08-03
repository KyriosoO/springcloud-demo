package com.dylan.esquery.web;

public final class KnowledgeSearchExceptions {
	private KnowledgeSearchExceptions() {
	}

	public static final class KnowledgeInvalidRequestException extends RuntimeException {
		public KnowledgeInvalidRequestException() { super("Invalid Knowledge search request"); }
		public KnowledgeInvalidRequestException(Throwable cause) { super("Invalid Knowledge search request", cause); }
	}

	public static final class KnowledgeForbiddenException extends RuntimeException {
		public KnowledgeForbiddenException() { super("Knowledge read is forbidden"); }
	}

	public static final class KnowledgeAuthorityUnavailableException extends RuntimeException {
		public KnowledgeAuthorityUnavailableException() { super("Knowledge read authority is unavailable"); }
	}

	public static final class KnowledgeProviderException extends RuntimeException {
		public KnowledgeProviderException(Throwable cause) { super("Knowledge provider failed", cause); }
		public KnowledgeProviderException() { super("Knowledge provider failed"); }
	}

	public static final class KnowledgeRateLimitedException extends RuntimeException {
		public KnowledgeRateLimitedException() { super("Knowledge provider rate limited"); }
	}

	public static final class KnowledgeTimeoutException extends RuntimeException {
		public KnowledgeTimeoutException(Throwable cause) { super("Knowledge provider timed out", cause); }
	}
}
