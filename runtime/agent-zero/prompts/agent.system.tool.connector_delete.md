### connector_delete
prepare or execute a connector delete operation
arg: `connector_id` connector id
arg: `payload` object describing what to delete
arg: `confirmed` boolean; required as `true` only after the user confirms the preview
returns confirmation-required preview for risky deletes, or a real setup/unsupported result

Never set `confirmed: true` unless the user has confirmed the exact preview.
