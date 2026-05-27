# Vini Canvas

Vini Canvas is the in-shell app-builder direction for Vini AI.

The Dyad source is imported under `dyad/` and rebranded at package metadata level as `vini-canvas`. The current runtime sidebar opens the existing real builder surface through the `Canvas` button while the full Dyad main-process and IPC services are adapted into the Vini runtime.

The project owner stated that Vini AI has permission to proceed with the full Dyad integration, including commercial competing use. Preserve Dyad attribution and upstream notice files while integrating the code.

## Open Design catalog

Vini Canvas imports the Open Design catalog as read-only guidance for design
selection and workflow planning:

- 133 Open Design skills from `open_design_catalog/skills`
- 150 Open Design design systems from `open_design_catalog/design-systems`
- Source commit and import metadata in `open_design_catalog/manifest.json`
- License and attribution in `THIRD_PARTY_NOTICES.md`

The catalog is not executed as trusted code. During generation, Canvas selects
relevant skills/design systems, creates a Vini Design Director brief, persists
that metadata into the project manifest, and injects the selected guidance into
the model prompt before writing real project files.
