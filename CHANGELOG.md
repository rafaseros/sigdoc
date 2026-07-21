# Changelog

All notable changes to SigDoc are documented in this file. The format loosely
follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions
adhere to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

The user-facing (Spanish) rendition of these entries lives in
`frontend/src/shared/version.ts` and is shown in-app via the "Novedades"
dialog. Keep both in sync when cutting a release.

## [4.0.0] — Documents from examples and related documents

### Added

- Create templates from an example document by selecting the variable text.
- Related documents per template that share variables (e.g. contract + receipt).
- Joint multi-document generation in a single flow.
- Version visible on every generated document.
- Download the template file of any version.
- Attach related documents from an example, reusing existing variables.

## [3.0.0] — Smart data

### Added

- Saved data (presets) per template for reusable values.
- Computed variables: formulas and amount-in-words.
- Document preview with watermark.
- Full document editor.
- Template guide and on-screen help.

## [2.0.0] — Organization and collaboration

### Added

- Private templates with per-user sharing.
- Per-plan usage limits.
- Personal folders for organizing templates.
- Rename and describe templates.
- Table view and pagination.

## [1.0.0] — System foundation

### Added

- .docx templates with `{{ }}` variables.
- Single and bulk generation from Excel.
- PDF export.
- Multi-company support with roles (admin / creator / generator).
- Action audit log.
