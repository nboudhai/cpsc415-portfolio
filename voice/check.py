"""Check a transcript in plain code. No model, no key.

A transcript is model output, and it can be confidently wrong in the places that
matter to a recruiter — names and numbers. These are the checks a program can make
without hearing the audio:

  * how far the words drift from what was said, as a word error rate (behavior 7);
  * whether the words that had to survive did (behavior 8);
  * whether anything came back at all (behavior 5).

Nothing here calls a model, so every test of this module is free to run.
"""
import re
from dataclasses import dataclass, field

_WORD = re.compile(r"[a-z0-9']+")

DEFAULT_MAX_WER = 0.15


def words(text: str | None) -> list[str]:
    """Lower-case words with punctuation removed, so 'Hello,  World!' == 'hello world'.

    The curly apostrophe is folded to a straight one first, so a word is not split
    in two by typography.
    """
    return _WORD.findall((text or "").lower().replace("’", "'"))


def wer(expected: str, got: str | None) -> float:
    """Word error rate: edits (insert, delete, substitute) per expected word.

    0.0 is a perfect transcript. 1.0 means nothing matched. An empty transcript
    scores 1.0, because every expected word is missing.
    """
    e, g = words(expected), words(got)
    if not e:
        return 0.0 if not g else 1.0
    # one row of the edit-distance table at a time; the rows are the expected words
    previous = list(range(len(g) + 1))
    for i, ew in enumerate(e, 1):
        current = [i]
        for j, gw in enumerate(g, 1):
            current.append(min(previous[j] + 1,           # delete the expected word
                               current[j - 1] + 1,        # insert a word that was heard
                               previous[j - 1] + (ew != gw)))  # or substitute it
        previous = current
    return previous[-1] / len(e)


@dataclass(frozen=True)
class Verdict:
    """The verdict recorded for one clip: the rate, the words that had to survive
    and did not, and whether the clip passed."""
    ok: bool
    wer: float
    missing: list[str] = field(default_factory=list)
    empty: bool = False


def compare(expected: str, got: str | None, must_contain: list[str] | None = None,
            max_wer: float = DEFAULT_MAX_WER) -> Verdict:
    """Compare one transcript with the text that was said.

    A clip passes only when the rate is within tolerance and no word that must
    survive is missing. The words are compared with their spacing and case
    folded away, so 'Receipt Reader' and 'receiptreader' both satisfy 'receipt
    reader' — but the rate still counts a split word as an edit.

    An empty transcript is a failed transcript, not a crash: it comes back as a
    verdict with ok=False.
    """
    heard = "".join(words(got))
    missing = [w for w in (must_contain or []) if "".join(words(w)) not in heard]
    rate = wer(expected, got)
    empty = not words(got)
    return Verdict(ok=rate <= max_wer and not missing and not empty,
                   wer=rate,
                   missing=missing,
                   empty=empty)
