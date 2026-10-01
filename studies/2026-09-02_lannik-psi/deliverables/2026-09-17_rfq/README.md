# Lannik Psi antenna RFQ, as issued

The antenna RFQ package and its internal companion as they stood when the RFQ
was issued, at commit 1d6ed0c ("Lannik Psi design study snapshot for the
RFQ"). These files are a record and are not edited. Later discussion with the
supplier produces new, separately dated documents.

## Sent to the supplier

- [TECHNICAL_DESCRIPTION.pdf](TECHNICAL_DESCRIPTION.pdf): the technical
  description, dated 17 September 2026. Its Markdown source is
  [TECHNICAL_DESCRIPTION.md](TECHNICAL_DESCRIPTION.md), with the figures in
  [figures/](figures/).
- [antenna_arr_77_TX_rev_A.mat](antenna_arr_77_TX_rev_A.mat): the reference TX
  excitation sent with it, byte-identical to
  [`inputs/antenna_arr_77_TX_rev_A.mat`](../../inputs/antenna_arr_77_TX_rev_A.mat).

## Internal, not sent

- [internal/REVIEW.md](internal/REVIEW.md) and its PDF: rationale for the
  technical description, reconciliation with the supplier presentation, and
  the decisions left open at issue.

## How the files were produced

The figures came from the study's 77 GHz model through a figure script, and
the PDFs from the Markdown through Pandoc and Typst with the template and
filter kept in [tools/](tools/). The figure script and the build script were
not kept here: they rebuilt the figures from the current study code, which has
since changed (centre frequency 76.5 GHz, loss assumptions). To rebuild, check
out 1d6ed0c, where the package lived under `studies/2026-09-02_lannik-psi/rfq/`.
The export comments at the top of the two Markdown files and the relative
paths in the internal review refer to that location.
