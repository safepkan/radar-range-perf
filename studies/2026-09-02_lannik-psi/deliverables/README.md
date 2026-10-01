# Delivered outputs of the Lannik Psi study

Reviewed figures and documents that were published outside the repository,
archived with the code state that produced them. Archived deliverables are
not edited afterwards; a revised version is a new, separately dated folder. Working figures stay under
`generated/` (gitignored) and are regenerated with `make study_260902_lannik_psi`
from the repository root. Whether to archive a fuller set of outputs is decided
when the study concludes, not at intermediate commits.

| Folder | Delivered | Contents |
|---|---|---|
| `2026-09-03_slack/` | Slack, 2026-09-03 12:00 | Horizontal Pd coverage and TX/RX best-beam cuts for the 2.42λ and 1.71λ square RX subarray candidates, from the 2026-09-03 state of `lannik_psi.py`. |
| `2026-09-10_presentation/` | Internal decision meeting, 2026-09-10 | The Marp deck as presented, its PDF and HTML exports, and the two figures it shows. |
| `2026-09-17_rfq/` | Antenna supplier, RFQ; technical description dated 2026-09-17 | The technical description as issued (PDF, Markdown source, figures), the reference TX excitation sent with it, the internal review, and the Pandoc/Typst template. Issued and immutable; see its README. |
| `2026-10-01_conclusion/` | Study README, 2026-10-01 | Single-scan Pd coverage at the study's conclusion: the two-variant summary figure embedded in the README, and the large-RX horizontal, vertical and diagonal maps, from `lannik_psi.py` at the concluding commit. |
