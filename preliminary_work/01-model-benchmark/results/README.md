# Versioned benchmark results

`legacy/` is a byte-for-byte copy of the first model and Pi capability probes previously stored only under
`~/logs/pithos`. These runs predate the campaign schema and remain labelled as legacy evidence.

New executions are exported automatically into `campaigns/<campaign_id>/`. Every versioned campaign contains
all textual raw artifacts; only the reconstructible SQLite database is excluded.
