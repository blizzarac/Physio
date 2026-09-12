# Authored content

Pain-pattern and mobilization entries, one Markdown file per entry with YAML
frontmatter (design doc §9). The API hot-reloads this directory; the build pipeline
validates every entry against the FMA import and refuses to emit a bundle if an
entry references an unknown structure, lacks a `source`, or fails the schema in
`pipeline/schemas.py`.

```
content/
  pain/            type: pain_pattern
  mobilization/    type: mobilization
  sources.yaml     bibliography keyed by the short IDs used in `sources:`
  disclaimer.md    rendered on every Pain and Mobilization tab
```

Only files inside subdirectories are treated as entries; top-level files are
documentation.

All content is educational and descriptive. It is not diagnosis or treatment
advice; entries should describe patterns reported in the cited literature and list
red flags that warrant professional assessment.
