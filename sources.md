# Job sources: tips and notes

The list of sites to search is in `config.json → sources` (edit it in the control panel, **Sites** tab).
Each site has `enabled`, `needs_signin`, `search` (a URL template or instructions), `apply` and `notes`.
URL placeholders: `{query}` (a search term), `{location}` (`search_location`), `{days}` (`search_window_days`),
`{seconds}` (the same window in seconds, for LinkedIn).

- "Sign-in" sites are opened in Claude in Chrome (the candidate's own Chrome, where they are signed in).
  Public sites: WebSearch / WebFetch / the built-in browser.
- If a site has no date filter, look at the last 7 days; the tracker drops duplicates.
- A site that shows a CAPTCHA or "verify you are human": stop, skip it this run, and say so in the report.

## Found during runs
<!-- The agent appends useful findings here: new boards, channels, groups, and tips on how a site behaves.
     New sites also go into config.json → sources with "enabled": false, for the candidate to switch on. -->
- Comeet forms live in an iframe: open https://www.comeet.co/jobs/<company-uid>/<position-uid>/apply directly
  (the uids are in the page HTML: comeet-company-uid / position-uid).
- BambooHR forms show a reCAPTCHA on submit: fill everything, then mark the job `manual`.
- Indeed and some aggregators show Cloudflare checks to automated browsers; skip them that run.
- Gemini results: in tests only about 1 in 6 links was a real open job, so always open and check each one.
