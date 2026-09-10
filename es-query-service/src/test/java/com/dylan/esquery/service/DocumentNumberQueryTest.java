package com.dylan.esquery.service;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.time.Duration;
import java.util.List;
import java.util.stream.IntStream;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

class DocumentNumberQueryTest {
	@ParameterizedTest
	@ValueSource(strings = {"甲乙〔2031〕07号", "甲乙[2031]07号", "甲乙公告2031年第07号",
			"甲 乙 公告2031年第07号", "请分别查找甲乙〔2031〕07号", "麻烦帮我同时比较甲乙〔2031〕07号"})
	void matchesOnlyTheLiteralIssuerAndNumberWithOptionalSpaces(String query) {
		List<String> patterns = DocumentNumberQuery.patterns(query);
		assertThat(patterns).hasSize(1);
		String canonical = query.substring(query.indexOf("甲")).replace(" ", "");
		assertThat(canonical).matches(patterns.getFirst());
		assertThat(canonical.replace("甲乙", "甲 　乙")).matches(patterns.getFirst());
		assertThat(canonical.replace("甲乙", "丙丁")).doesNotMatch(patterns.getFirst());
		assertThat(canonical.replace("07号", "7号")).doesNotMatch(patterns.getFirst());
		assertThat(canonical.replace("2031", "2032")).doesNotMatch(patterns.getFirst());
		assertThat(patterns.getFirst()).doesNotContain(".*");
	}

	@ParameterizedTest
	@ValueSource(strings = {"、", "和", "与", "或", "以及", " 和　"})
	void inheritsOnlyAnAdjacentAnnouncementIssuer(String connector) {
		List<String> patterns = DocumentNumberQuery.patterns("甲乙公告2031年第07号" + connector + "2032年第8号");
		assertThat(patterns).hasSize(2);
		assertThat("甲乙公告2032年第8号").matches(patterns.get(1));
		assertThat("丙丁公告2032年第8号").doesNotMatch(patterns.get(1));
	}

	@Test
	void adjacentLegacyAndDifferentFullIssuersRetainTheirIdentity() {
		List<String> patterns = DocumentNumberQuery.patterns("甲乙〔2031〕07号和[2032]8号、丙丁公告2033年第9号以及2034年第10号");
		assertThat(patterns).hasSize(4);
		assertThat("甲乙[2032]8号").matches(patterns.get(1));
		assertThat("丙丁公告2033年第9号").matches(patterns.get(2));
		assertThat("丙丁公告2034年第10号").matches(patterns.get(3));
		assertThat("甲乙公告2034年第10号").doesNotMatch(patterns.get(3));
	}

	@ParameterizedTest
	@ValueSource(strings = {"", " ", "　", " 　"})
	void completeReferencesStartAtTheEndOfThePreviousReference(String separator) {
		List<String> references = List.of("甲乙公告2031年第07号", "甲乙公告2032年第8号", "丙丁〔2033〕9号");
		List<String> patterns = DocumentNumberQuery.patterns(String.join(separator, references));
		assertThat(patterns).hasSize(references.size());
		for (int index = 0; index < references.size(); index++) {
			assertThat(references.get(index)).matches(patterns.get(index));
			assertThat("错误机关公告2032年第8号").doesNotMatch(patterns.get(index));
		}
	}

	@Test
	void completeReferenceScanningRetainsWholeSignalLimitsAndStableDeduplication() {
		String four = "甲乙〔2031〕1号 甲乙[2032]2号 丙丁公告2033年第3号 戊己公告2034年第4号";
		assertThat(DocumentNumberQuery.patterns(four)).hasSize(4);
		assertThat(DocumentNumberQuery.patterns(four + " 戊己公告2034年第4号"))
				.isEqualTo(DocumentNumberQuery.patterns(four));
		assertThat(DocumentNumberQuery.patterns(four + " 庚辛〔2035〕5号")).isEmpty();
		assertThat(DocumentNumberQuery.patterns("甲乙〔2031〕1号 " + "丙".repeat(49) + "〔2032〕2号")).isEmpty();
	}

	@ParameterizedTest
	@ValueSource(strings = {" 2032年第8号", "，2032年第8号", "执行期限 2032年第8号执行期限"})
	void aNewScanBoundaryDoesNotAuthorizeShorthandInheritance(String tail) {
		assertThat(DocumentNumberQuery.patterns("甲乙公告2031年第07号" + tail)).singleElement()
				.satisfies(pattern -> assertThat("甲乙公告2032年第8号").doesNotMatch(pattern));
	}

	@ParameterizedTest
	@ValueSource(strings = {"。2032年第8号", "和随后发布的2032年第8号", "和第8号", "和〔2032〕8号"})
	void doesNotGuessUnknownOrNonAdjacentShorthand(String tail) {
		assertThat(DocumentNumberQuery.patterns("甲乙公告2031年第07号" + tail)).hasSize(1);
	}

	@Test
	void preservesCaseRegionBracketsAndDeduplicatesInOrder() {
		List<String> patterns = DocumentNumberQuery.patterns("甲省AB〔2031〕07号、甲省AB〔2031〕07号");
		assertThat(patterns).hasSize(1);
		assertThat("甲省AB〔2031〕07号").matches(patterns.getFirst());
		for (String wrong : List.of("甲省ab〔2031〕07号", "乙省AB〔2031〕07号", "AB〔2031〕07号", "甲省AB[2031]07号")) {
			assertThat(wrong).doesNotMatch(patterns.getFirst());
		}
		assertThat(DocumentNumberQuery.patterns("和田〔2031〕1号")).hasSize(1);
	}

	@ParameterizedTest
	@ValueSource(strings = {"甲〔2031〕1号", "甲乙〔2031]1号", "甲乙[2031〕1号", "甲乙〔２０３１〕1号",
			"甲乙.*〔2031〕1号", "甲乙[0-9]号", "甲乙/.*公告2031年第1号", "甲乙〔2031〕1234567890123号", "普通政策问题"})
	void rejectsUnsupportedIdentifiersWithoutTreatingInputAsRegex(String query) {
		assertThat(DocumentNumberQuery.patterns(query)).isEmpty();
	}

	@Test
	void limitsApplyToTheWholeSignalAndNeverMatchAnIssuerSuffix() {
		assertThat(DocumentNumberQuery.patterns("甲".repeat(48) + "〔2031〕1号")).hasSize(1);
		assertThat(DocumentNumberQuery.patterns("甲".repeat(49) + "〔2031〕1号")).isEmpty();
		assertThat(DocumentNumberQuery.patterns("甲乙〔2031〕1号、" + "丁".repeat(49) + "〔2031〕2号")).isEmpty();
		assertThat(DocumentNumberQuery.patterns("甲乙〔2031〕1号、〔2031〕2号、〔2031〕3号、〔2031〕4号、〔2031〕5号")).isEmpty();
		assertThat(DocumentNumberQuery.patterns("甲乙〔2031〕1号" + "。".repeat(1024))).isEmpty();
		assertThat(DocumentNumberQuery.patterns(null)).isEmpty();
		org.junit.jupiter.api.Assertions.assertTimeout(Duration.ofSeconds(2), () ->
				assertThat(DocumentNumberQuery.patterns("甲".repeat(1000) + "[2031]1号")).isEmpty());
	}

	@Test
	void stripsOnePreambleAndHonorsCodePointAndListBoundaries() {
		String reference = "甲乙〔2031〕1号";
		String bounded = reference + "。".repeat(1024 - reference.length());
		assertThat(DocumentNumberQuery.patterns(bounded)).hasSize(1);
		assertThat(DocumentNumberQuery.patterns(bounded + "。")).isEmpty();
		List<String> twice = DocumentNumberQuery.patterns("查询查询" + reference);
		assertThat(twice).singleElement().satisfies(pattern -> {
			assertThat("查询" + reference).matches(pattern);
			assertThat(reference).doesNotMatch(pattern);
		});
		assertThat(DocumentNumberQuery.patterns(reference + "、〔2031〕2号、〔2031〕3号、〔2031〕4号、〔2031〕4号")).hasSize(4);
		String supplementaryHan = new String(Character.toChars(0x20000)).repeat(48);
		assertThat(DocumentNumberQuery.patterns(supplementaryHan + "〔2031〕1号")).singleElement()
				.satisfies(pattern -> assertThat(supplementaryHan + "〔2031〕1号").matches(pattern));
	}

	@Test
	void patternsAreImmutableAndRequestLocal() {
		List<String> expected = DocumentNumberQuery.patterns("甲乙〔2031〕1号");
		assertThatThrownBy(() -> expected.add("injected")).isInstanceOf(UnsupportedOperationException.class);
		IntStream.range(0, 64).parallel().forEach(index -> {
			String source = "甲乙〔2031〕" + index + "号";
			assertThat(DocumentNumberQuery.patterns(source)).singleElement().satisfies(pattern -> assertThat(source).matches(pattern));
		});
		assertThat(DocumentNumberQuery.patterns("甲乙〔2031〕1号")).isEqualTo(expected);
	}
}
