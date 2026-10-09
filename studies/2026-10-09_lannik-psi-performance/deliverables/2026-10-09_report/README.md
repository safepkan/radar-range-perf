# Lannik Psi range performance, as posted

The study's README as it was posted internally on Slack on 9 October 2026.
These files are a record and are not edited.

- [Lannik_Psi_range_performance.pdf](Lannik_Psi_range_performance.pdf): the
  document, rendered from the study's [README.md](../../README.md) at the
  commit that added this folder.
- [SLACK_POST_SV.md](SLACK_POST_SV.md): the Slack message posted with it, in
  Swedish.

The PDF came from the Markdown through Pandoc and Typst, with the template and
filter in [tools/](tools/), adapted from the CARKIT report's. The filter turns
links into the repository into plain text and drops Pandoc's figure captions,
since each figure's caption is the paragraph below it. From the study folder:

```sh
pandoc README.md --from=markdown --pdf-engine=typst \
    --template=deliverables/2026-10-09_report/tools/document.typst \
    --lua-filter=deliverables/2026-10-09_report/tools/report.lua \
    --output=deliverables/2026-10-09_report/Lannik_Psi_range_performance.pdf
```

The figures come from [psi_performance.py](../../psi_performance.py), which
needs no raw data.
