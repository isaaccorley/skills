"""Regression tests for every false-accusation bug found in real bibliographies.

Each test locks down one specific defect that, before it was fixed, reported a
correct citation as fabricated. That is the failure mode this skill exists to
avoid, so the suite is written accusation-first: most assertions are of the form
"this correct entry must NOT be flagged".

Offline and stdlib-only — no network, no pytest required:

    python3 -m unittest discover -s tests -v      # from the skill root
    pytest tests/                                 # also works

Any test needing an API answer builds the ``Record`` by hand instead of fetching
it, so the suite stays runnable when Semantic Scholar is down (it was, for the
whole final day of development) and when OpenAlex has burned its daily budget.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from audit_refs import bind_is_credible  # noqa: E402
from bibmeta import (  # noqa: E402
    Record,
    delatex,
    family_key,
    family_keys,
    norm_text,
    title_coverage,
    title_ratio,
)
from bibstyle import author_list_tells, generation_signal, style_findings  # noqa: E402
from refparse import (  # noqa: E402
    detect_marker,
    dewrap,
    is_anonymized,
    is_grey_literature,
    printed_doi,
    split_references,
    strip_line_numbers,
    strip_repeated_lines,
)
from triage import P1_INVENTED, P2_FABRICATED, P4_STYLE, Finding, render_ranked  # noqa: E402
from validate_refs import (  # noqa: E402
    Entry,
    detect_arxiv_id,
    parse_authors_bibtex,
    parse_fields,
    unescape_identifier,
)


def rec(title: str, families: list[str], source: str = "crossref:search", year: str = "2020") -> Record:
    return Record(source=source, title=title, families=families, year=year)


class TestBindCredibility(unittest.TestCase):
    """The worst bug of the project: asymmetric coverage bound real papers to
    unrelated works whose titles happened to be *shorter*, then reported the real
    authors as invented. It was also nondeterministic — the Transformer case only
    fired when S2 was throttled and the run fell through to Crossref search.
    """

    def test_shorter_registrar_title_does_not_bind(self):
        # "Graph based image segmentation" (an unrelated master's thesis) is fully
        # contained in the reference title, so one-directional coverage scored
        # 1.000 and the bind was accepted.
        ref = {
            "title": "Efficient graph-based image segmentation",
            "authors": ["Felzenszwalb, P.", "Huttenlocher, D."],
        }
        thesis = rec("Graph based image segmentation", ["Chan"])
        self.assertFalse(bind_is_credible(thesis, ref))

    def test_question_mark_variant_does_not_bind(self):
        # A 2025 book chapter titled "Is Attention All You Need?" bound to the
        # Transformer paper and reported all eight real authors as invented.
        ref = {
            "title": "Attention is all you need",
            "authors": ["Vaswani, A.", "Shazeer, N.", "Parmar, N."],
        }
        chapter = rec("Is Attention All You Need?", ["Mancini"], year="2025")
        self.assertFalse(bind_is_credible(chapter, ref))

    def test_real_paper_still_binds(self):
        # The guard must not be so tight that correct binds break.
        ref = {
            "title": "Attention is all you need",
            "authors": ["Vaswani, A.", "Shazeer, N.", "Parmar, N."],
        }
        real = rec("Attention is All you Need", ["Vaswani", "Shazeer", "Parmar", "Uszkoreit"], year="2017")
        self.assertTrue(bind_is_credible(real, ref))

    def test_author_overlap_required_when_reference_names_authors(self):
        # Zero author overlap was the cheapest reliable discriminator: every
        # wrong bind observed in testing had none.
        ref = {"title": "Deep residual learning for image recognition", "authors": ["He, K."]}
        same_title_wrong_people = rec("Deep residual learning for image recognition", ["Nakamura"])
        self.assertFalse(bind_is_credible(same_title_wrong_people, ref))

    def test_missing_authors_falls_back_to_title_only(self):
        # Grey literature and some styles print no authors; requiring overlap
        # unconditionally would make those unbindable by construction.
        ref = {"title": "Deep residual learning for image recognition", "authors": []}
        cand = rec("Deep Residual Learning for Image Recognition", ["He", "Zhang"])
        self.assertTrue(bind_is_credible(cand, ref))

    def test_empty_title_never_binds(self):
        self.assertFalse(bind_is_credible(rec("Anything", ["X"]), {"title": "", "authors": []}))


class TestNameFolding(unittest.TestCase):
    """Diacritics broke author comparison in both directions: non-decomposing
    letters got treated as word separators, and German/Nordic names are spelled
    two legitimate ways across sources.
    """

    def test_eszett_does_not_truncate_to_one_letter(self):
        # family_key("Straße") returned "e" — the ß became a word separator, so
        # the "surname" was its own last fragment.
        self.assertEqual(family_key("Straße"), "strasse")

    def test_transliterated_and_native_spellings_match(self):
        # The same author publishes as Rußwurm and Russwurm; both must key alike.
        self.assertTrue(family_keys("Rußwurm") & family_keys("Russwurm"))

    def test_umlaut_expansion_and_collapse_both_offered(self):
        # ä->ae (German convention) and ä->a (accent stripping) both occur.
        self.assertTrue(family_keys("Müller") & family_keys("Mueller"))
        self.assertTrue(family_keys("Müller") & family_keys("Muller"))

    def test_multiword_surname_matches_either_order(self):
        # "Carlos Riquelme Ruiz" vs "Riquelme, Carlos" — a real Crossref/bib
        # disagreement on a compound Spanish surname.
        self.assertTrue(family_keys("Carlos Riquelme Ruiz") & family_keys("Riquelme, Carlos"))

    def test_unrelated_names_do_not_match(self):
        # The folding must not be so generous that everything collides.
        self.assertFalse(family_keys("Thomas Brox") & family_keys("Kingma, D."))

    def test_latex_accents_decode_before_brace_stripping(self):
        # Decoding after brace-stripping degraded Gon{\c{c}}alves to
        # "Gon\ccalves", keying as "ccalves" — a permanent false MISMATCH.
        self.assertTrue(family_keys(delatex(r"Gon{\c{c}}alves") ) & family_keys("Gonçalves"))
        self.assertTrue(family_keys(delatex(r"H{\"a}nsch")) & family_keys("Hänsch"))


class TestTitleComparison(unittest.TestCase):
    def test_html_entities_unescaped(self):
        # SPIE deposits titles wrapped in escaped markup; the junk inflated the
        # denominator so a fully-present title read as a mismatch at 0.757.
        self.assertEqual(
            norm_text("&lt;title&gt;Cloud detection&lt;/title&gt;"), norm_text("Cloud detection")
        )

    def test_coverage_is_symmetric_in_practice(self):
        short, long = "Graph based image segmentation", "Efficient graph-based image segmentation"
        # One direction saturates; that is precisely why both are required.
        self.assertGreater(title_coverage(short, long), 0.95)
        self.assertLess(title_coverage(long, short), 0.95)

    def test_case_and_punctuation_insensitive(self):
        self.assertGreater(title_ratio("Attention Is All You Need", "attention is all you need!"), 0.98)


class TestIdentifierExtraction(unittest.TestCase):
    """Identifier damage always manufactures fabrication verdicts, never hides
    them, so every one of these was a false accusation on a live paper.
    """

    def test_latex_escaped_doi_unescapes(self):
        # DBLP escapes underscores for LaTeX: 10.1162/tacl\_a\_00276 404s.
        self.assertEqual(unescape_identifier(r"10.1162/tacl\_a\_00276"), "10.1162/tacl_a_00276")

    def test_arxiv_id_found_outside_eprint(self):
        # detect_arxiv_id originally read only `eprint` and missed 53% of the IDs
        # in a real 332-entry bibliography (24 found -> 199 after the fix).
        # Scholar puts the ID in `journal`, DBLP in `volume` as abs/NNNN.NNNNN.
        cases = [
            ({"eprint": "1711.05101"}, "1711.05101"),
            ({"doi": "10.48550/arXiv.2103.00020"}, "2103.00020"),
            ({"journal": "arXiv preprint arXiv:1505.04597"}, "1505.04597"),
            ({"volume": "abs/1810.04805"}, "1810.04805"),
            # The version suffix is stripped: arXiv's id_list accepts either, and
            # the unversioned form is what the bib should carry.
            ({"note": "arXiv:2005.14165v4"}, "2005.14165"),
        ]
        for fields, expected in cases:
            with self.subTest(fields=fields):
                got = detect_arxiv_id(Entry(key="k", etype="article", fields=fields, raw=""))
                self.assertEqual(got, expected)

    def test_old_style_arxiv_id(self):
        entry = Entry(key="k", etype="article", fields={"eprint": "cs/0701001"}, raw="")
        self.assertEqual(detect_arxiv_id(entry), "cs/0701001")

    def test_no_arxiv_id_when_absent(self):
        entry = Entry(key="k", etype="article", fields={"journal": "Nature"}, raw="")
        self.assertIsNone(detect_arxiv_id(entry))

    def test_longest_doi_wins(self):
        # A page break can leave a corrupted and an intact copy in the same
        # reference; damage always shortens, so the longest match is the real one.
        ref = "Title. doi:10.1038/s41597- and again doi:10.1038/s41597-026-07099-1"
        self.assertEqual(printed_doi(ref), "10.1038/s41597-026-07099-1")

    def test_dewrap_never_de_hyphenates_inside_a_doi(self):
        # 10.1038/s41597- + 026-07099-1 became s41597026-07099-1: a dead DOI on
        # a live paper. The identifier check must precede de-hyphenation.
        joined = dewrap(["Smith et al. Some paper. doi:10.1038/s41597-", "026-07099-1"])
        self.assertIn("10.1038/s41597-026-07099-1", joined)

    def test_dewrap_still_de_hyphenates_prose(self):
        joined = dewrap(["A large-scale study of graph-", "based segmentation methods"])
        self.assertIn("graphbased", joined.replace(" ", ""))

    def test_others_token_is_not_a_surname(self):
        # Keying "others" as a surname made every abbreviated entry report an
        # author present in the bib but absent from the registry record — i.e.
        # the invented-author signal, on a correct entry.
        self.assertEqual(parse_authors_bibtex("Smith, J. and others"), ["Smith, J."])


class TestReferenceSplitting(unittest.TestCase):
    """Bad splitting strands real first authors, and an orphaned fragment
    resolves to a paper whose first author looks missing.
    """

    def test_marker_style_is_sticky_against_prose_heuristic(self):
        # "a line starting Surname," split a [N] list mid-author-list: "Huy V." /
        # "Vo, Marc Sbai, ..." is one name across a wrap.
        # Needs >=3 markers to be recognised as an enumeration (see
        # test_marker_detection_needs_three_markers for that boundary).
        text = "\n".join([
            "[1] Huy V.",
            "Vo, Marc Sbai, and others. Some paper title. In CVPR, 2021.",
            "[2] Jane Roe. Another paper. In ICCV, 2022.",
            "[3] A. Smith. Third paper. In ECCV, 2020.",
            "[4] B. Jones. Fourth paper. In NeurIPS, 2019.",
        ])
        refs = split_references(text)
        self.assertEqual(len(refs), 4)
        # The wrapped author name must rejoin, not strand "Huy V." as an orphan.
        self.assertIn("Huy V. Vo", refs[0])

    def test_marker_detection_needs_three_markers(self):
        # Documented boundary, not a bug worth chasing: a list of one or two
        # references has no enumeration to detect, so it falls through to the
        # prose heuristic. Real bibliographies are far past this threshold; a
        # two-item paste is the only thing affected.
        self.assertIsNone(detect_marker(["[1] One paper.", "[2] Two papers."]))
        self.assertIsNotNone(detect_marker(["[1] One.", "[2] Two.", "[3] Three."]))

    def test_prose_path_content_loss_is_a_known_limitation(self):
        # KNOWN LIMITATION of the legacy path, asserted so it cannot silently get
        # worse. Author-year lists (ICLR/ACL/NeurIPS) print no markers, so
        # splitting falls to the prose heuristic, which reads a capitalised
        # continuation line ("NeurIPS, 2017.") as a new reference and drops it.
        # SKILL.md records a 26% loss (74 refs -> 55) from this on a real paper.
        # It is why audit_refs.py (human extraction) is the recommended path and
        # why the legacy path must never be trusted for a fabrication verdict.
        text = "\n".join([
            "Kingma, D. P. and Ba, J. Adam: A method for stochastic",
            "optimization. In ICLR, 2015.",
            "Vaswani, A., Shazeer, N. Attention is all you need. In",
            "NeurIPS, 2017.",
            "He, K., Zhang, X. Deep residual learning. In CVPR, 2016.",
        ])
        refs = split_references(text)
        joined = " ".join(refs)
        # Titles survive, which is what the audit actually compares on...
        for token in ("Adam", "Attention is all you need", "Deep residual learning"):
            self.assertIn(token, joined)
        # ...but the wrapped venue tail is lost. If this assertion ever fails
        # because the loss is GONE, delete the test and celebrate.
        self.assertNotIn("NeurIPS, 2017", joined)

    def test_parenthesised_year_is_not_a_marker(self):
        # Wrapped lines opening with "(2021) pp. 1016--1022" passed as (N)
        # markers; two test papers collapsed from 50 and 25 refs to 9 and 5.
        lines = [
            "(2021) pp. 1016--1022",
            "(2019) pp. 1--10",
            "(2020) pp. 55--60",
        ]
        self.assertIsNone(detect_marker(lines))

    def test_real_numbered_markers_detected(self):
        lines = ["[1] First paper.", "[2] Second paper.", "[3] Third paper."]
        self.assertIsNotNone(detect_marker(lines))

    def test_non_ascii_surname_marker(self):
        # "13. Şimşek, F.F.: ..." failed an ASCII letter lookahead and merged
        # silently into reference 12.
        lines = ["1. Adams, A.: A paper.", "2. Şimşek, F.F.: Another paper.", "3. Brown, B.: Third."]
        marker = detect_marker(lines)
        self.assertIsNotNone(marker)
        self.assertTrue(marker.match(lines[1]))

    def test_line_numbers_stripped_both_shapes(self):
        # Review submissions carry margin line numbers, which pdftotext
        # interleaves. Unstripped, the leading one reads as a list marker.
        paired = "279  References  279\n280  [1] A paper. In CVPR, 2021.  280"
        cleaned = strip_line_numbers(paired)
        self.assertNotIn("279", cleaned)
        self.assertIn("References", cleaned)

    def test_real_marker_survives_line_number_stripping(self):
        text = "1. Adams, A.: A paper.\n2. Brown, B.: Another paper.\n3. Clark, C.: Third paper."
        self.assertIn("1.", strip_line_numbers(text))

    def test_running_header_stripped_at_line_level(self):
        # The subtlest bug of the set: dropping page furniture only AFTER
        # grouping let a header splice into the middle of a title, dropping the
        # title match to 0.18 and escalating a correct entry to [FABRICATED].
        text = "\n".join([
            "ICCV 2026 Submission #1234",
            "[1] Sentinel-2: ESA's optical high-resolution mission for",
            "ICCV 2026 Submission #1234",
            "GMES operational services. In RSE, 2012.",
            "ICCV 2026 Submission #1234",
            "[2] Another paper. In CVPR, 2021.",
            "ICCV 2026 Submission #1234",
            "[3] A third paper. In ECCV, 2020.",
            "[4] A fourth paper. In NeurIPS, 2019.",
        ])
        cleaned = strip_repeated_lines(text)
        self.assertNotIn("Submission #1234", cleaned)
        refs = split_references(cleaned)
        self.assertEqual(len(refs), 4)
        self.assertIn("optical high-resolution mission for GMES operational services", refs[0])


class TestUnverifiableIsNotFabricated(unittest.TestCase):
    def test_anonymized_reference_detected(self):
        # A double-blind submission citing its own prior work is unresolvable by
        # design; flagging it reads as not understanding the review process.
        self.assertTrue(is_anonymized("Anonymous. Some title. Under review, 2025."))

    def test_grey_literature_detected(self):
        # Zenodo/agency/software citations 404 on DOI registries while being
        # entirely real. On one paper this was most of the top tier.
        self.assertTrue(is_grey_literature("NOAA. Bathymetric atlas. Technical report, 2019."))

    def test_ordinary_paper_is_neither(self):
        ref = "K. He, X. Zhang. Deep residual learning. In CVPR, 2016."
        self.assertFalse(is_anonymized(ref))
        self.assertFalse(is_grey_literature(ref))


class TestStyleChecks(unittest.TestCase):
    def test_protected_acronym_is_not_flagged(self):
        # "{{ChatML}}" is the CORRECT way to protect an all-caps token; flagging
        # it sent authors to "fix" properly-braced entries.
        found = style_findings("k", {"title": "{{ChatML}}"})
        self.assertFalse([f for f in found if "double-braced" in f.summary])

    def test_double_braced_multiword_title_is_flagged(self):
        # Must go through parse_fields: it strips one brace level, so a real
        # `title = {{...}}` reaches style_findings as `{...}`. Asserting against
        # the raw source string tests a state that never occurs.
        fields = parse_fields("title = {{Attention is all you need}}")
        self.assertEqual(fields["title"], "{Attention is all you need}")
        found = style_findings("k", fields)
        self.assertTrue([f for f in found if "double-braced" in f.summary])

    def test_single_hyphen_page_range(self):
        found = style_findings("k", {"pages": "35-49"})
        self.assertTrue([f for f in found if "hyphen" in f.summary])
        self.assertTrue(all(f.priority == P4_STYLE for f in found))

    def test_en_dash_page_range_is_clean(self):
        self.assertFalse([f for f in style_findings("k", {"pages": "35--49"}) if "hyphen" in f.summary])

    def test_doi_as_url_flagged(self):
        found = style_findings("k", {"doi": "https://doi.org/10.1109/CVPR.2016.90"})
        self.assertTrue([f for f in found if "URL" in f.summary or "url" in f.summary])

    def test_bare_doi_is_clean(self):
        self.assertFalse(style_findings("k", {"doi": "10.1109/CVPR.2016.90"}))

    def test_unspaced_initials_flagged(self):
        found = style_findings("k", {"author": "J.D. Owens"})
        self.assertTrue([f for f in found if "initials" in f.summary])

    def test_missing_identifier_is_not_a_finding(self):
        # This check produced 299 findings on a 332-entry bibliography and
        # drowned everything that mattered.
        self.assertEqual(style_findings("k", {"title": "A perfectly fine title"}), [])

    def test_and_others_on_small_paper_outranks_generic_case(self):
        few = author_list_tells("k", "Smith, J. and others", 3)
        many = author_list_tells("k", "Smith, J. and others", 40)
        self.assertTrue(few and many)
        self.assertIn("nothing to abbreviate", few[0].detail)

    def test_and_others_absent_yields_nothing(self):
        self.assertEqual(author_list_tells("k", "Smith, J. and Doe, A.", 2), [])

    def test_generation_signal_needs_two_entries(self):
        self.assertIsNone(generation_signal(["a"], 50))
        self.assertIsNotNone(generation_signal(["a", "b"], 50))


class TestTriageRendering(unittest.TestCase):
    def test_worst_tier_leads(self):
        findings = [
            Finding(P4_STYLE, "b", "page range uses a single hyphen"),
            Finding(P1_INVENTED, "a", "cited work not found anywhere"),
            Finding(P2_FABRICATED, "c", "DOI names no paper"),
        ]
        out = render_ranked(findings, total=10)
        self.assertLess(out.index("not found anywhere"), out.index("names no paper"))
        self.assertLess(out.index("names no paper"), out.index("single hyphen"))

    def test_clean_run_says_so(self):
        self.assertIn("No findings", render_ranked([], total=42))


if __name__ == "__main__":
    unittest.main()
