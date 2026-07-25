"""Rank bibliography findings by how much they matter.

A flat list of problems is the wrong output: "reference [31] does not exist" and
"pages use a single hyphen" are not the same kind of news, and mixing them in one
list invites the reader to dismiss the whole thing as pedantry. Four tiers, worst
first, chosen by what the finding costs if left alone:

P1  the cited work does not appear to exist         -> the claim it supports is unsupported
P2  a fabricated identifier, or an invented author  -> points at the wrong paper, or
                                                       credits someone falsely
P3  wrong metadata on a real, correctly-identified work
P4  formatting and style

The split between P2 and P3 is deliberate and is the one worth internalizing: an
identifier that names no paper (or names a different one) and an author who is
not on the paper are *integrity-shaped* problems, while a truncated author list
or a preprint-vs-published year is housekeeping. In a review they belong in
different paragraphs; in your own paper they belong in different work sessions.

Stdlib only, no network.
"""

from dataclasses import dataclass

P1_INVENTED = 1
P2_FABRICATED = 2
P3_METADATA = 3
P4_STYLE = 4

TIER_TITLES = {
    P1_INVENTED: "P1  Cited work not found anywhere - may not exist",
    P2_FABRICATED: "P2  Fabricated identifier or invented author",
    P3_METADATA: "P3  Wrong metadata on a real work",
    P4_STYLE: "P4  Formatting and style",
}

TIER_GUIDANCE = {
    P1_INVENTED: (
        "Verify by hand in a browser before acting. If it truly does not exist, the "
        "sentence citing it has no support - re-read the claim, do not just swap in a "
        "similar paper. In a review, raise a cluster of these with the editor separately "
        "from the technical comments."
    ),
    P2_FABRICATED: (
        "Fix the IDENTIFIER, never the title - editing a title to match a wrong DOI is "
        "how a fake citation becomes permanent. An author present in the entry but not on "
        "the registry record credits someone for work they did not do."
    ),
    P3_METADATA: (
        "Real paper, wrong details: truncated author lists, preprint-vs-published year "
        "drift, title punctuation. Replace the fields from the canonical source. Not an "
        "integrity issue - keep these out of the same paragraph as P1/P2 findings."
    ),
    P4_STYLE: (
        "Mechanical and safe to batch-fix last. None of these change which paper is "
        "cited."
    ),
}


@dataclass
class Finding:
    """One problem with one reference."""

    priority: int
    ref: str  # citation key, or "ref 12" for the PDF path
    summary: str
    detail: str = ""
    fix: str = ""

    def sort_key(self) -> tuple[int, str]:
        return (self.priority, self.ref)


def render_ranked(findings: list[Finding], total: int) -> str:
    """Render findings grouped by tier, worst first, with a fix-first line."""
    if not findings:
        return f"\nNo findings across {total} references.\n"

    lines: list[str] = ["", "=" * 72, f"RANKED FINDINGS ({len(findings)} across {total} references)", "=" * 72]

    by_tier: dict[int, list[Finding]] = {}
    for f in findings:
        by_tier.setdefault(f.priority, []).append(f)

    worst = min(by_tier)
    counts = ", ".join(
        f"{len(by_tier[t])}xP{t}" for t in sorted(by_tier)
    )
    lines.append(f"Start here: {TIER_TITLES[worst].split('  ', 1)[1]}  ({counts})")

    for tier in sorted(by_tier):
        group = sorted(by_tier[tier], key=Finding.sort_key)
        lines.append("")
        lines.append(f"--- {TIER_TITLES[tier]}  ({len(group)}) ---")
        lines.append(f"    {TIER_GUIDANCE[tier]}")
        lines.append("")
        for f in group:
            lines.append(f"  [{f.ref}] {f.summary}")
            if f.detail:
                for dl in f.detail.splitlines():
                    lines.append(f"        {dl}")
            if f.fix:
                lines.append(f"        fix: {f.fix}")
    lines.append("")
    return "\n".join(lines)
