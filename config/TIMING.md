# DTS timing

Merge these fields into the existing user config JSON; retain all other settings.
Source runs use `data/config.json`. Frozen installs use
`%LOCALAPPDATA%/AutoDrive/config.json`. Restart AutoDrive after editing.

```json
{
  "dts_poll_interval": 0.2,
  "dts_page_settle": 0.25,
  "dts_copy_timeout": 8.0,
  "dts_input_interval": 0.1,
  "dts_message_pause": 0.05,
  "dts_ui_settle": 0.3,
  "dts_focus_settle": 0.5,
  "dts_navigation_settle": 2.0,
  "dts_start_settle": 1.0,
  "dts_dialog_poll": 0.25
}
```

- `dts_poll_interval`: seconds between state checks (minimum 0.05).
- `dts_page_settle`: short UI settling delay in seconds (zero or greater).
- `dts_copy_timeout`: maximum wait per copy stage, not a fixed delay.
- `dts_input_interval`: interval between repeated Enter/Space key actions.
- `dts_message_pause`: pause between individual background key messages.
- `dts_ui_settle`: generic short UI action settling delay.
- `dts_focus_settle`: focus assignment and focus-control lookup delay.
- `dts_navigation_settle`: DTS navigation and confirmation settling delay.
- `dts_start_settle`: startup transition and flow retry delay.
- `dts_dialog_poll`: file-dialog discovery polling interval.

Missing values use defaults. Invalid, negative and non-finite values fall back
to defaults. A slower device can start with a 0.5-second settling delay.

Coverage: existing flow polling/page-settling waits and fault-code row copying.
Startup/scanning deadlines, recording durations and other application-specific
waits are independent. These fields are not a global speed multiplier.

Fault codes still use the existing row-by-row Copy button and consecutive-text
end heuristic. A fresh clipboard update and a closed confirmation dialog are
required for each row. Copy failures raise an error instead of accepting stale
data. First-row positioning and identical adjacent rows still need separate
live-DTS validation; this timing change does not solve those navigation limits.
