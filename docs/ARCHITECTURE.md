# Architecture

## Overview

PlotLab is a local Python desktop application that reads multiple Excel workbooks, combines them into editable series, previews a chart, and exports a publication-ready PNG.

## Data flow

```text
Excel folder
  -> data_loader
  -> SeriesData models
  -> editable combined table
  -> PlotConfig + plotting
  -> live Tkinter preview
  -> 300-DPI PNG / optional combined workbook
```

## Modules

- `app.py`: stable application entry point.
- `excel_plotter/gui.py`: main Tkinter workflow.
- `excel_plotter/data_loader.py`: workbook discovery and validation.
- `excel_plotter/models.py`: chart and data-series models.
- `excel_plotter/editable_data.py`: editable tabular representation.
- `excel_plotter/data_editor.py`: combined-data workbench.
- `excel_plotter/plotting.py`: Matplotlib figure construction and export.
- `excel_plotter/style_dialog.py`: chart parameter editor.
- `excel_plotter/preset_store.py`: per-user preset persistence.
- `tests/`: loader, editing, plotting, and preset regression tests.

## Data boundary

Input workbooks, exported images, combined workbooks, and user presets stay local. Test fixtures are the only data files intended for version control.
