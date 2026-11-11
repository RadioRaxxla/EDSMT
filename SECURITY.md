# Security

## Reporting a vulnerability

Please do not open a public issue for a vulnerability.

Use GitHub's private reporting: the **Security** tab of this repository, then
**Report a vulnerability**. The report goes to the maintainer only.

If that is unavailable, use the COMMS page on
[radioraxxla.com](https://www.radioraxxla.com/) and say only that you have a
security report; leave the detail for the reply.

You can expect an acknowledgement within a few days. A fix ships as a normal
numbered release, with the cause described in `CHANGELOG.md`.

Only the latest version is supported. EDSMT tells you on launch when a newer
build exists, and updating keeps your finds.

---

## Code signing

EDSMT is not code signed, which has two visible effects.

### SmartScreen warns on first run

Windows shows *"Windows protected your PC"* for any unsigned program it has not
seen downloaded often. It is a reputation check, not a detection.
**More info, then Run anyway.** The warning fades as more people install the
build and returns with each new release, because reputation attaches to the
file.

### VirusTotal

A few of the engines on VirusTotal flag each release. Those have been
machine-learning or heuristic detections, not signature matches. That pattern
is typical of PyInstaller builds, which unpack a Python runtime to a temporary
folder when they start.

If you would rather not run a binary, the project is GPL-3.0:
`EDSMT-source.zip` is published with every release, `RUN.bat` runs the app
directly from source, and the GitHub Actions workflow builds the same source on
a GitHub-hosted Windows runner with a public log.

---

## What the app does on your machine

- **It reads the game's files and writes nothing to them.** `Status.json`,
  `Journal.*.log`, `Market.json` and `Cargo.json` in your Saved Games folder
  are opened read-only.
- **Its own data is stored in `%LOCALAPPDATA%\RadioRaxxla\EDSMT`**, not in the
  program folder.
- **It listens on your own PC only, and only if you ask.** The OBS browser
  source is off until you switch it on. It then serves one page on
  `127.0.0.1`, which nothing outside your PC can reach. There is no remote
  control. Every other connection is an outbound HTTPS request that the app
  starts.
- **Updates are downloaded automatically and installed only when you choose.**
  The update check reads `version.json` on radioraxxla.com. A newer build is
  downloaded in the background under these rules, each covered by
  `tests/test_update.py`:
  - `version.json` must carry a valid signature. The app holds the public
    key; the private key stays on the build machine. A list that fails the
    check offers no download;
  - it must come from radioraxxla.com over HTTPS; a `version.json` naming any
    other host is refused, as is a redirect to one;
  - it is kept only if its size and SHA-256 match `version.json`, otherwise it
    is deleted and nothing is installed;
  - it is checked again at the moment it runs, so a file altered on disk after
    download is refused;
  - it runs only when you press INSTALL UPDATE, never in the middle of a
    session.

  The signature shows who wrote the list of checksums, so a file changed on
  the website is refused. That is separate from Windows code signing, which
  EDSMT still does not have (above).
  Settings has a switch to download new versions only on request.
- **Global hotkeys.** By default Left Alt with the number row, and the same
  numbers with AltGr (Ctrl+Alt); all can be rebound. They are registered with
  Windows so they work while the game is in front, and they capture those key
  combinations only, not what you type.
- **Credentials.** Any credential you enter, such as your Inara API key or a
  Discord webhook address, is stored in `settings.json` in your own
  `%LOCALAPPDATA%` and sent only to the service it belongs to. Settings shows
  them as dots until you press **Show**, and hides them again after 20 seconds.
  The key the community map gives this copy of EDSMT (below) is kept in the
  same folder and is never shown.
- **HTTPS is checked against your system's certificates** that are still in
  date. Windows keeps certificates after they run out; EDSMT leaves those out.

## What leaves your machine

- **Your finds.** The position, commodity, density, rig count and body facts of
  each deposit you record, with a timestamp, and the prices at markets you
  open. This is what the community map is made of, so sharing it is not a
  switch. **Every find carries your CMDR name.** EDSMT reads it from the
  game's journal; it is never typed and cannot be left off. There is no
  account and no sign-up.
- **The leaderboard.** Your CMDR name and points are on the community
  leaderboard until you press Leave in the Leaderboard window.
- **A key for this copy of EDSMT.** On first run the community map gives the
  app a random key, and the app sends it with each request. It tells one
  installation from another, so one that misbehaves can be turned away. It
  says nothing about you.
- **What you search for**, and the system you are in when you ask for results
  near you.
- **The wing link.** In a wing in the game, EDSMT links you with each wingmate
  who runs EDSMT and has you in their wing too. Settings has the switch, and a
  typed code does the same outside a wing. While linked, your system, body,
  surface position, heading, SRV state and rig positions are sent every few
  seconds with your CMDR name. Nothing is stored; you are dropped two minutes
  after your last update.
- **Mining locations go to EDDN**, the network other Elite tools read.
  Settings has the switch; it is on to start with. When the FSS finds mining
  locations on a body, that body's signal counts are sent with your CMDR name
  as the uploader. No finds, no position on the body, no credits.
- **Squadron share is off unless you switch it on.** It goes to your
  squadron's site only: your carrier's location and jumps, its buy and sell
  orders, your Powerplay rank and merits, and the hauling tonnage you deliver
  to builds. Never credits, carrier finance, prices paid, your FID or chat.
- **Discord.** A webhook you add posts your finds or sessions to your own
  channel, from your PC straight to Discord. Rich Presence is off to start
  with; it tells the Discord app on your PC what you are doing and does not
  use the network itself.
- **Pairing with your Radio Raxxla member page** happens only when you type a
  code from that page into EDSMT.
- **Inara reporting is off unless you enter your own Inara API key.** The key
  is sent to inara.cz and nowhere else.

`settings.json` holds credentials and should not be attached to a bug report.
The issue template asks for the status line instead.

---

## The community service

`edsmt.radioraxxla.com` (and its first address, `api.radioraxxla.com`) is
operated by Radio Raxxla and is the only community service EDSMT connects to. Report a problem with it the same way as any other
vulnerability.
