"""The checker's tests, from spec.md's Week 7 behaviors 5, 7, and 8.

No key, no network, nothing billed: the checker is plain code.

Behavior 5  an empty transcript is a failed transcript, not a crash.
Behavior 7  expected text is compared in code, by word error rate, with a stated
            tolerance (0.15 by default, max_wer per clip); a clip passes only
            when the rate is within tolerance and no word that must survive is
            missing.
Behavior 8  each clip's must_contain list names the words that must survive, the
            list differs per clip, and a missing one is reported even when the
            rate is within tolerance.
"""
import json
import pathlib

import pytest
from check import compare, wer, words

CLIPS = pathlib.Path(__file__).resolve().parents[1] / "clips" / "expected.json"

THIRTEEN = "what broke in your receipt reader project and which skills have you shipped"


def test_a_perfect_transcript_scores_zero_and_passes():
    """Behavior 7: the easy case."""
    v = compare(THIRTEEN, THIRTEEN)
    assert v.wer == 0.0
    assert v.ok
    assert not v.missing
    assert not v.empty


def test_wer_counts_edits_per_expected_word():
    """Behavior 7: the rate is edits per expected word, not per word heard."""
    assert wer(THIRTEEN, THIRTEEN) == 0.0
    assert wer(THIRTEEN, THIRTEEN.replace("broke", "breaks")) == pytest.approx(1 / 13)
    # a word heard that was never said is an insertion, and counts the same way
    assert wer(THIRTEEN, THIRTEEN + " indeed") == pytest.approx(1 / 13)


def test_max_wer_overrides_the_default_tolerance_per_clip():
    """Behavior 7: the default is 0.15 and max_wer in expected.json overrides it.

    The course's clip-02 is the real case: Whisper split 'bootcamp' into two
    words and appended 'Music' to the trailing silence — three edits in sixteen
    words — so that clip's own tolerance was raised to 0.2.
    """
    expected = ("have you ever deployed anything with kubernetes be honest i'm "
                "comparing you with a bootcamp graduate")
    got = expected.replace("a bootcamp graduate", "a boot camp graduate music")
    assert compare(expected, got).wer == pytest.approx(3 / 16)   # the course recorded 0.188
    assert not compare(expected, got).ok            # 0.1875 is outside the 0.15 default
    assert compare(expected, got, max_wer=0.2).ok   # the clip's own tolerance


def test_an_empty_transcript_is_a_failed_transcript_not_a_crash():
    """Behavior 5: a verdict, not an exception."""
    v = compare(THIRTEEN, "")
    assert v.empty
    assert v.wer == 1.0
    assert not v.ok
    # a transcript that never arrived is the same thing
    assert compare(THIRTEEN, None).empty


def test_a_missing_name_is_reported_even_when_the_rate_is_within_tolerance():
    """Behavior 8: the named-word check is independent of the rate."""
    expected = "my name is nadia boudhaim maguire and what salary would you expect for your first job"
    v = compare(expected, expected.replace("maguire", "mcguire"),
                must_contain=["Nadia", "Boudhaim", "Maguire"])
    assert v.wer <= 0.15        # the rate is fine
    assert v.missing == ["Maguire"]
    assert not v.ok


def test_a_number_read_as_words_is_a_miss():
    """Behavior 8: the words that must survive include a number."""
    expected = ("which skills from cpsc 415 have you actually shipped in the course "
                "so far this semester in the spring")
    v = compare(expected, expected.replace("cpsc 415", "cpsc four fifteen"),
                must_contain=["415"])
    assert v.wer <= 0.15        # the rate is fine
    assert v.missing == ["415"]
    assert not v.ok


def test_each_clip_names_its_own_words_that_must_survive():
    """Behavior 8: the list differs per clip and comes from expected.json."""
    clips = json.loads(CLIPS.read_text(encoding="utf-8"))
    assert len(clips) >= 2
    lists = [tuple(clip["must_contain"]) for clip in clips]
    assert len(set(lists)) == len(lists), "the lists must differ per clip"
    for clip in clips:
        for word in clip["must_contain"]:
            without = clip["text"].replace(word, "")
            v = compare(clip["text"], without, must_contain=[word])
            assert v.missing == [word], f"{clip['file']}: {word!r} should be reported missing"


def test_extra_whitespace_and_capitalization_do_not_count():
    """The words are compared after lower-casing and dropping punctuation."""
    assert words("Hello,  World!") == ["hello", "world"]
    assert compare("hello world", "Hello,  World!").wer == 0.0


def test_a_split_word_is_an_edit():
    """'boot camp' for 'bootcamp' is an edit, not a formatting difference: the
    word was substituted and a second word inserted, so two edits."""
    v = compare("the bootcamp ran fast", "the boot camp ran fast")
    assert v.wer == pytest.approx(2 / 4)


def test_a_split_word_costs_an_edit_but_still_survives_as_a_word():
    """The course's clip-02: Whisper split 'bootcamp' into two words, which is why
    that clip's tolerance was raised to 0.2 — the word itself still survived."""
    v = compare("the bootcamp ran fast", "the boot camp ran fast", must_contain=["bootcamp"])
    assert v.missing == []
    assert v.wer == pytest.approx(2 / 4)


def test_a_number_written_without_a_space_still_survives():
    """'CPSC415' for 'CPSC 415' costs two edits in the rate and survives as a word."""
    v = compare("which skills from cpsc 415 have you shipped",
                "which skills from cpsc415 have you shipped", must_contain=["415"])
    assert v.missing == []
    assert v.wer == pytest.approx(2 / 8)
