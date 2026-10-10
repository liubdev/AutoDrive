# Bundled reference manual

`md1cs089_v6.html` is an unchanged copy of the user-supplied
`MD1CS089故障排查手册_V6.html`. SHA-256:
`1da283ae2239d7813e0edc559b828e4e6eabcd0db04a00b256cfc2bde5d2f7d6`.

This is a static reference, not a generated diagnosis. It is available from
the diagnosis results and historical report details via the reference tab.
Its conclusions are not imported into the current vehicle's report or exports.

The reader loads the local file with Qt WebEngine on first use. All diagrams
and styles are embedded in the HTML; no network access is needed. The
existing `ui/assets` cx_Freeze include rule bundles the document. Keep the
Qt WebEngine includes in `setup.py` so its helper process and resources are
collected by the cx_Freeze Qt hooks.
