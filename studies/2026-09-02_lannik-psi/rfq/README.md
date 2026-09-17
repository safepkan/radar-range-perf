# Lannik Psi antenna RFQ material

Working technical attachment for supplier discussion and quotation. This folder
is separate from the exploratory study and the archived delivered presentations.
It has not been sent to a supplier by the repository tooling.

## Documents and sharing

- [TECHNICAL_DESCRIPTION.pdf](TECHNICAL_DESCRIPTION.pdf): the current illustrated
  attachment, five pages of main text plus three technical appendices.
- [TECHNICAL_DESCRIPTION.md](TECHNICAL_DESCRIPTION.md): editable source, usable
  directly in a Markdown viewer. It replaces the former study-root
  `ANTENNA_REQUIREMENTS.md`.
- [Reference TX excitation](../inputs/antenna_arr_77_TX_rev_A.mat): send this
  alongside the technical description under its existing filename. The source
  remains in the study's inputs; Appendix A explains its schema and limitations.
- [internal/REVIEW.md](internal/REVIEW.md): internal rationale, presentation
  reconciliation and open decisions, also available as
  [internal/REVIEW.pdf](internal/REVIEW.pdf). These are not part of the supplier
  attachment.

The reference deck is not needed to understand the technical description.
Exact mechanical interfaces are covered by the separately defined interface
material; they are not redefined here. The old reading/test PDFs were removed.
Any later issued version should be archived under the study's `deliverables/`
with its date and supporting figures, following that folder's convention.

## Figures and reproduction

The four figures under `figures/` are generated specifically for this document:
TX modes, selected RX geometry, reference TX taper and reference TX beam cuts.
PNG versions support Markdown viewers; SVG versions are embedded in the PDF.
The taper and beam cuts use the supplied 77 GHz excitation through the existing
study functions; the geometry uses the selected H/4 stagger and square layouts.
The original study models and generated working plots are unchanged.

From the repository root:

```sh
sh studies/2026-09-02_lannik-psi/rfq/tools/build.sh
```

The script activates `venv/`, regenerates the figures, and renders both PDFs using
existing `pandoc` and `typst` executables. It installs nothing. The renderer uses
DejaVu Sans and DejaVu Sans Mono. These tools/fonts must already be available.
The Markdown is never rewritten by the export. Explicit page divisions are
HTML comments interpreted by `tools/pagebreak.lua`; the PDF styling is in
`tools/document.typst`.

Each document's Markdown starts with a comment giving its PDF-only export
command. The review uses the same template with `--metadata=internal-review:true`
to set its PDF title and running header to identify it as internal material.

For figure generation alone, with the repository environment activated:

```sh
source venv/bin/activate
MPLBACKEND=Agg venv/bin/python studies/2026-09-02_lannik-psi/rfq/tools/render_figures.py
```

Changes to the Python generator should be followed by the repository's
`venv/bin/python pre_commit.py`. Visually inspect the exported PDF after content
or layout changes; an export succeeding does not guarantee readable pagination.
