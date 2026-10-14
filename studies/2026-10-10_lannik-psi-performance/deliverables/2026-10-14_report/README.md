# Lannik Psi range performance, as issued

The study's README as issued internally on 14 October 2026, with its Slack
message. These files are a record and are not edited.

It replaced a version posted on 10 October in the same Slack post, whose
message gained a note on the change. The numbers are the same; the opening
now describes Lannik Psi as a long-range, narrow-beam radar instead of naming
an application, and "Not yet established" adds the signal-processing chain in
detail. The 10 October version is in commit d239aef, in the folder
`deliverables/2026-10-10_report/`.

- [Lannik_Psi_range_performance.pdf](Lannik_Psi_range_performance.pdf): the
  document, rendered from the study's [README.md](../../README.md) at the
  commit that added this folder.
- [SLACK_POST_SV.md](SLACK_POST_SV.md): the Slack message that posts it, in
  Swedish, with the note on the change at the end.

The PDF came from the Markdown through Pandoc and Typst, with the template and
filter in [tools/](tools/), adapted from the CARKIT report's. The filter turns
links into the repository into plain text, keeping the file's name for a link
to one of its sections, and drops Pandoc's figure captions, since each
figure's caption is the paragraph below it. From the study folder:

```sh
pandoc README.md --from=markdown --pdf-engine=typst \
    --template=deliverables/2026-10-14_report/tools/document.typst \
    --lua-filter=deliverables/2026-10-14_report/tools/report.lua \
    --output=deliverables/2026-10-14_report/Lannik_Psi_range_performance.pdf
```

The figures are the study's tracked ones from 10 October, drawn by
[psi_performance.py](../../psi_performance.py), which needs no raw data.
