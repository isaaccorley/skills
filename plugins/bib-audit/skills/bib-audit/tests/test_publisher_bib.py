"""Tests for publisher_bib.py: parsing and converting publisher citation exports.

Each test pins one quirk seen in a real export (Nature, PLOS, Frontiers, NEJM, PubMed,
Copernicus, arXiv). Offline and stdlib-only, like the rest of the suite:

    python3 -m unittest discover -s tests -v      # from the skill root
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from publisher_bib import (  # noqa: E402
    compare,
    is_group,
    known_urls,
    name_split,
    parse_bib,
    parse_export,
    to_bibtex,
)

BIB_ENTRY = parse_bib(
    """@article{moetal2021,
  author  = {Mo, Yin and Eyre, David W. and {Oxford COVID infection review team} and Cooper, Ben S.},
  title   = {Transmission of community- and hospital-acquired {SARS-CoV-2} in hospital settings},
  journal = {PLOS Medicine},
  volume  = {18},
  number  = {10},
  pages   = {e1003816},
  year    = {2021},
  doi     = {10.1371/journal.pmed.1003816}
}"""
)[0]


def diffs(out):
    return [msg for lvl, msg in out if lvl == "DIFF"]


class FormatParsing(unittest.TestCase):
    def test_bibtex_upper_and_and_unbraced_group(self):
        # PLOS writes " AND " between names and leaves a group author unbraced.
        rec, fmt = parse_export(
            "@article{x,\n author = {Mo, Yin AND Eyre, David W. AND "
            "Oxford COVID infection review team AND Cooper, Ben S.},\n"
            " title = {Transmission of community- and hospital-acquired SARS-CoV-2 in hospital "
            "settings},\n journal = {PLOS Medicine}, volume = {18}, number = {10},\n"
            " pages = {e1003816}, year = {2021}, doi = {10.1371/journal.pmed.1003816}}"
        )
        self.assertEqual(fmt, "BibTeX")
        self.assertIn("{Oxford COVID infection review team}", rec["fields"]["author"])
        self.assertEqual(diffs(compare(rec["fields"], BIB_ENTRY["fields"], "bib")), [])

    def test_ris_doi_in_m3_and_empty_end_page(self):
        # PLOS RIS: the DOI sits in M3 ("doi:..."), SP is the article number, EP is empty.
        rec, fmt = parse_export(
            "TY  - JOUR\nT1  - Transmission\nA1  - Mo, Yin\nJF  - PLOS Medicine\nVL  - 18\n"
            "IS  - 10\nSP  - e1003816\nEP  - \nY1  - 2021/10/12\n"
            "M3  - doi:10.1371/journal.pmed.1003816\nER  - \n"
        )
        self.assertEqual(fmt, "RIS")
        f = rec["fields"]
        self.assertEqual(f["pages"], "e1003816")
        self.assertEqual(f["doi"], "10.1371/journal.pmed.1003816")
        self.assertEqual(f["year"], "2021")

    def test_endnote_keeps_repeated_authors_for_the_compare_to_flag(self):
        # Nature's export repeats consortium members; deduplicating would hide the error.
        rec, fmt = parse_export(
            "%0 Journal Article\n%T Characterising transmission\n%A Lindsey, Benjamin B.\n"
            "%A Shah, Dhruv R.\n%A Shah, Dhruv R.\n%J Nature Communications\n%V 13\n%P 671\n"
            "%D 2022\n%R 10.1038/s41467-022-28291-y\n"
        )
        self.assertEqual(fmt, "EndNote")
        bib = {"author": "Lindsey, Benjamin B. and Shah, Dhruv R."}
        self.assertTrue(
            any("repeats: shah" in m for m in diffs(compare(rec["fields"], bib, "bib")))
        )

    def test_refworks(self):
        rec, fmt = parse_export(
            "RT Journal Article\nA1 Mo, Yin\nT1 Transmission\nJF PLOS Medicine\nVO 18\n"
            "IS 10\nSP e1003816\nYR 2021\nDO 10.1371/journal.pmed.1003816\n"
        )
        self.assertEqual(fmt, "RefWorks")
        self.assertEqual(rec["fields"]["volume"], "18")

    def test_medline_group_author_first_and_investigators_dropped(self):
        # NEJM's RECOVERY paper in PubMed: CN (the group) precedes FAU, and IR/FIR list
        # thousands of investigators who are not authors.
        rec, fmt = parse_export(
            "PMID- 32678530\nTI  - Dexamethasone in Hospitalized Patients with Covid-19.\n"
            "LID - 10.1056/NEJMoa2021436 [doi]\nCN  - RECOVERY Collaborative Group\n"
            "FAU - Horby, Peter\nAU  - Horby P\nJT  - The New England journal of medicine\n"
            "VI  - 384\nIP  - 8\nPG  - 693-704\nDP  - 2021 Feb 25\n"
            "IR  - Smith J\nFIR - Smith, John\n"
        )
        self.assertEqual(fmt, "MEDLINE")
        f = rec["fields"]
        self.assertEqual(f["author"], "{RECOVERY Collaborative Group} and Horby, Peter")
        self.assertEqual(f["title"], "Dexamethasone in Hospitalized Patients with Covid-19")
        self.assertEqual(
            (f["pages"], f["doi"], f["year"]), ("693--704", "10.1056/NEJMoa2021436", "2021")
        )

    def test_csl_json_crossref_type(self):
        # doi.org content negotiation returns type "journal-article", not "article-journal".
        rec, fmt = parse_export(
            '{"type": "journal-article", "title": "Case characteristics",'
            ' "author": [{"family": "Karagiannidis", "given": "Christian"}, {"name": "ISARIC4C"}],'
            ' "container-title": "The Lancet Respiratory Medicine", "volume": "8",'
            ' "issue": "9", "page": "853-862", "DOI": "10.1016/S2213-2600(20)30316-7",'
            ' "issued": {"date-parts": [[2020, 9]]}}'
        )
        self.assertEqual((fmt, rec["type"]), ("CSL-JSON", "article"))
        self.assertEqual(rec["fields"]["author"], "Karagiannidis, Christian and {ISARIC4C}")

    def test_plain_text_and_html_are_not_exports(self):
        self.assertEqual(
            parse_export("Mo Y, Eyre DW. Transmission. PLoS Med. 2021;18:e1003816."),
            (None, "plain text"),
        )
        self.assertEqual(
            parse_export("<!DOCTYPE html><html><head><title>Just a moment"), (None, None)
        )


class Names(unittest.TestCase):
    def test_group_or_person(self):
        # arXiv writes "Given Family" with no comma; a word count alone misread these as groups.
        self.assertFalse(is_group("Prescott C. Alexander"))
        self.assertFalse(is_group("Lindsey, Benjamin B."))
        self.assertTrue(is_group("Oxford COVID infection review team"))
        self.assertTrue(is_group("The COVID-19 Genomics UK (COG-UK) consortium"))

    def test_three_part_name_and_leading_the(self):
        self.assertEqual(name_split("Longini, Jr, Ira M."), ("longini", "Ira M."))
        self.assertEqual(
            name_split("{The RECOVERY Collaborative Group}")[0],
            name_split("RECOVERY Collaborative Group")[0],
        )


class Compare(unittest.TestCase):
    def test_frontiers_volume_string_is_reported(self):
        out = compare({"volume": "Volume 12 - 2022"}, {"volume": "12"}, "bib")
        self.assertEqual(diffs(out), ['volume: export "Volume 12 - 2022", bib "12"'])

    def test_placeholder_author_is_reported(self):
        # NEJM's BibTeX export gives author = {null null} for a group-authored paper.
        out = compare(
            {"author": "null null"}, {"author": "{The RECOVERY Collaborative Group}"}, "bib"
        )
        self.assertTrue(any("not in the bib" in m and "null" in m for m in diffs(out)))

    def test_conversion_round_trip(self):
        rec, _ = parse_export("TY  - JOUR\nT1  - A title\nA1  - Doe, Jane\nPY  - 2020\nER  - \n")
        back = parse_bib(to_bibtex(rec, "doe2020"))[0]
        self.assertEqual((back["key"], back["fields"]["author"]), ("doe2020", "Doe, Jane"))


class Routing(unittest.TestCase):
    def test_known_endpoints(self):
        self.assertIn(
            "citation-needed.springer.com", known_urls("doi", "10.1038/s41467-022-28291-y")[0]
        )
        # PLOS BibTeX gives the PDF page range ("1-20"); its RIS has the article number.
        self.assertIn("/citation/ris?", known_urls("doi", "10.1371/journal.pmed.1003816")[0])
        self.assertTrue(known_urls("doi", "10.5194/gmd-17-1-2024")[0].endswith("gmd-17-1-2024.bib"))
        self.assertEqual(known_urls("arxiv", "2504.03604"), ["https://arxiv.org/bibtex/2504.03604"])
        self.assertEqual(known_urls("doi", "10.1016/j.foo.2020.1"), [])


if __name__ == "__main__":
    unittest.main()
