# CARKIT validation report, as issued

The study's report as issued internally on 10 October 2026, with its Slack
message. These files are a record and are not edited.

- [CARKIT_validation_report.pdf](CARKIT_validation_report.pdf): the report,
  rendered from the study's [README.md](../../README.md) at the commit that
  added this folder.
- [SLACK_POST_SV.md](SLACK_POST_SV.md): the Slack message that posts it, in
  Swedish.

The PDF came from the Markdown through Pandoc and Typst, with the template and
filter in [tools/](tools/). The filter turns links into the repository into
plain text, keeping the file's name for a link to one of its sections, and
drops Pandoc's figure captions, since each figure's caption is the paragraph
below it. From the study folder:

```sh
pandoc README.md --from=markdown --pdf-engine=typst \
    --template=deliverables/2026-10-10_report/tools/document.typst \
    --lua-filter=deliverables/2026-10-10_report/tools/report.lua \
    --output=deliverables/2026-10-10_report/CARKIT_validation_report.pdf
```

The report's figures come from [report_figures.py](../../report_figures.py),
which needs only the study's tracked summaries.
