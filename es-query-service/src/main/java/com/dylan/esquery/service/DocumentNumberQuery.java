package com.dylan.esquery.service;

import java.util.LinkedHashSet;
import java.util.List;
import java.util.Set;
import java.util.StringJoiner;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/** Optional metadata signal, not a query planner or an issuer identity resolver. */
final class DocumentNumberQuery {
	private static final String ISSUER = "[\\p{IsHan}A-Za-z]+?";
	private static final String LEGACY = "(?:〔[0-9]{4}〕|\\[[0-9]{4}\\])[0-9]+号";
	private static final String ANNOUNCEMENT = "公告[0-9]{4}年第[0-9]+号";
	private static final String FULL = "(" + ISSUER + ")(" + ANNOUNCEMENT + "|" + LEGACY + ")";
	private static final Pattern SEARCH = Pattern.compile("(?<![\\p{IsHan}A-Za-z0-9])" + FULL);
	private static final Pattern ITEM = Pattern.compile(FULL);
	private static final Pattern LEGACY_ITEM = Pattern.compile(LEGACY);
	private static final Pattern ANNOUNCEMENT_ITEM = Pattern.compile("[0-9]{4}年第[0-9]+号");
	private static final Pattern CONNECTOR = Pattern.compile("(?:、|和|与|或|以及)");
	private static final Pattern PREAMBLE = Pattern.compile(
			"^(?:请(?:帮我)?|帮我|麻烦(?:帮我)?)?(?:分别|同时)?(?:查找|查询|检索|查阅|查看|对比|比较)");
	private static final Pattern NUMBER = Pattern.compile(
			"(?:公告[0-9]{4}年第|〔[0-9]{4}〕|\\[[0-9]{4}\\])[0-9]{1,12}号");

	private DocumentNumberQuery() {
	}

	static List<String> patterns(String query) {
		if (query == null || query.codePointCount(0, query.length()) > 1024) {
			return List.of();
		}
		String compact = query.replace(" ", "").replace("　", "");
		Set<String> references = new LinkedHashSet<>();
		Matcher search = SEARCH.matcher(compact);
		int cursor = 0;
		while (search.find(cursor)) {
			Reference previous = fullReference(search);
			if (!add(references, previous)) {
				return List.of();
			}
			cursor = search.end();
			while (cursor < compact.length()) {
				Matcher connector = at(CONNECTOR, compact, cursor);
				if (!connector.lookingAt()) {
					break;
				}
				cursor = connector.end();
				Matcher item = at(ITEM, compact, cursor);
				Reference next;
				if (item.lookingAt()) {
					next = fullReference(item);
				} else {
					boolean announcement = previous.number().startsWith("公告");
					item = at(announcement ? ANNOUNCEMENT_ITEM : LEGACY_ITEM, compact, cursor);
					if (!item.lookingAt()) {
						break; // Never borrow an issuer across arbitrary intervening text.
					}
					next = new Reference(previous.issuer(), (announcement ? "公告" : "") + item.group());
				}
				if (!add(references, next)) {
					return List.of();
				}
				previous = next;
				cursor = item.end();
			}
		}
		return references.stream().map(DocumentNumberQuery::whitespacePattern).toList();
	}

	private static Matcher at(Pattern pattern, String input, int start) {
		return pattern.matcher(input).region(start, input.length());
	}

	private static Reference fullReference(Matcher match) {
		return new Reference(PREAMBLE.matcher(match.group(1)).replaceFirst(""), match.group(2));
	}

	private static boolean add(Set<String> references, Reference reference) {
		int issuerLength = reference.issuer().codePointCount(0, reference.issuer().length());
		String canonical = reference.issuer() + reference.number();
		if (issuerLength < 2 || issuerLength > 48 || !NUMBER.matcher(reference.number()).matches()
				|| canonical.codePointCount(0, canonical.length()) > 80
				|| whitespacePattern(canonical).length() > 900) {
			return false;
		}
		references.add(canonical);
		return references.size() <= 4; // Overflow disables the whole signal, never truncates the list.
	}

	private static String whitespacePattern(String reference) {
		StringJoiner joined = new StringJoiner("[ 　]*");
		reference.codePoints().forEach(codePoint -> {
			String literal = new String(Character.toChars(codePoint));
			joined.add(codePoint == '[' || codePoint == ']' ? "\\" + literal : literal);
		});
		return joined.toString();
	}

	private record Reference(String issuer, String number) {
	}
}
