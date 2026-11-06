# 3EO motion-design preview

A private, silent 15-second Remotion prototype about internal links, at 1080×1920 / 30fps.
Three page illustrations enter, relevant edges draw, a cursor clicks a link and a packet follows
the edge to a highlighted destination. A gentle camera move and Persian headings explain the
mechanism. These are original schematic illustrations, not real browser capture or SEO results.

## Preview

Use Node 24 and npm. In this directory:

```sh
npm ci
npm run dev -- --no-open
```

Open the exact Studio address printed by the command, then select `InternalLinks`. The current
development instance uses http://localhost:3000/InternalLinks inside the cloud workspace only.
This address is not a verified user-accessible preview: the founder reported a blank page.
Do not present a successful loopback/browser smoke test as evidence the remote viewer can open
it. A 15-second MP4 was rendered and delivered through the authorized private Telegram bot
for this visual review instead. `PageCard` is also registered as
a connected composition for independent editing. Headings, page cards, links, cursor and camera
are named timeline layers. Fonts are local, with the upstream DejaVu license included. There
are no remote images, paid calls, synthetic speech or source-video assets.

`npm run lint` runs ESLint and TypeScript. `npm run build` bundles the preview. Still-frame
inspection uses `npx remotion still src/index.ts InternalLinks out/check.png --frame=240
--browser-executable=/usr/bin/chromium`; the browser option is specific to this cloud image.
No complete MP4 is exported by default; use Studio's render controls when export is requested.
Generated output is ignored by Git.

## Scope

This is a design prototype for review, separate from the bot's existing Pillow/FFmpeg renderer.
It does not yet make every arbitrary scenario into a Remotion video. It needs narration, more
scene families and tested integration before it can replace production templates. The previous
text-card sample was rejected; this prototype is not founder-approved. Do not use automatic
asset generation as evidence of editorial acceptance. Existing source/script/video approval
gates, production restrictions and private media handling remain in force.

Remotion 4.0.541 and React versions are locked. The installed Remotion license permits evaluation;
verify the relevant individual/team commercial eligibility before production use. No license
purchase or hosted rendering service is used here. Processes must be restarted after cloud
snapshot restoration; this Studio is not permanent hosting.
