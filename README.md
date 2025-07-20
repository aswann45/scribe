# scribe

> Rapid DOCX generation from Jinja2 templates – YAML + pydantic + Typer

`scribe` turns structured data (YAML / JSON / CSV / Excel) into polished Microsoft Word documents using **docxtpl** templates.  
It targets bulk workflows (tens - hundreds of files) yet remains friendly for single-document scripting.

---

## Installation

```bash
pip install scribe     # from PyPI (coming soon)
# or from source
pip install -e .
```
Python 3.10 + and LibreOffice/Microsoft Word (to open the results) are
required. On first use it will create `outputs/` directory next to the project root.

## Quick Start

```bash
# see registered templates
$ scribe list-templates
• annual_report         templates/annual_report.docx

# scan disk for unregistered templates
$ scribe list-templates --all

# generate one file
$ scribe generate annual_report data/report.yaml

# bulk render from CSV (one row per document)
$ scribe generate annual_report data/bulk.csv --delimiter ';'
```

### Global flags: 

| flag                         | default | description                       |
| ---------------------------- | ------- | --------------------------------- |
| `--log-level`                | INFO    | DEBUG / INFO / WARNING / ERROR    |
| `--log-json / --no-log-json` | -       | one-line JSON logs (for CI / k8s) |


### Discover and register new templates

```bash
$ scribe discover-templates
✓ 3 template(s) written to config/discovered_templates.yaml
# merge the snippet into config/app.yaml
```

## Public API (import and use in your own scripts)

```python
from pathlib import Path
from decimal import Decimal

from scribe import (
    DataLoader,
    TemplateFinder,
    get_settings,
    make_context,
    generate_docx,
)

# 1) pick a template
tpl_cfg = TemplateFinder().discover()[0]        # annual_report

# 2) load data
raw = DataLoader.load(Path("data/report.yaml"))  # dict or list[dict]

# 3) validate via side-car schema (if any)
ctx = make_context(tpl_cfg.path, raw)            # BaseDocContext or subclass

# 4) render
out_path = generate_docx(ctx, tpl_cfg, Path("outputs"))
print("wrote", out_path)
```

## Configuration

| source | precedence |
| ------ | ---------- |
| **CLI kwargs** | highest |
| `SCRIBE_*` environment variables | |
| `.env` file in CWD | |
| `config/app.yaml` | base |

### Environment variables
| name | example | purpose |
| ---- | ------- | ------- |
| `SCRIBE_OUTPUT_DIR` | `/tmp/reports` | override default outputs dir |
| `SCRIBE_TEMPLATES_DIR` | `/srv/docx:/opt/private` (path-sep list) | additional template search roots |
| `SCRIBE_LOG_JSON` | `1` | enable JSON logs in any context |


## Template validation (optional)

Add a file next to your template:

```yaml
# templates/annual_report.schema.yaml
client_name: str
report_date: date
summary: str
revenue: Decimal
details: List[scribe.models.custom:Detail]
```

`make_context` will generate a Pydantic model on the fly and coerce/validate incoming data before rendering.

## Rich text/conditional styling

`config/app.yaml`
```yaml
templates:
  - name: annual_report
    path: templates/annual_report.docx
    output_naming: "{client_name}_{report_date:%Y%m%d}.docx"
    options:
      richtext:
        status:
          - when: { equals: "APPROVED" }
            style: { bold: true, color: "008000" }
          - when: { equals: "REJECTED" }
            style: { bold: true, color: "CC0000" }
```
In your DOCX reference {{ richtext_status }} to get coloured text; the plain {{ status }} remains unchanged.

## Development & tests

```bash
# Linting & type-checking
ruff check scribe
mypy scribe

# Test suite
pytest -q --cov=scribe
```

### Commit conventions
- Black-formatted, fully-typed code
- NumPy-style docstrings
- CI matrix: Python 3.10 & 3.11

Feel free to open issues or PRs – contributions welcome!