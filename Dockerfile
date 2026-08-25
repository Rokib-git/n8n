# Official Playwright image already includes Chromium + every OS dependency
# it needs (fonts, codecs, etc). Building this yourself without it is the
# single most common source of "works on my machine" pain with headless
# browsers, so it's worth using even though the image is a few hundred MB.
FROM mcr.microsoft.com/playwright:v1.45.0-jammy

WORKDIR /app

COPY package.json ./
RUN npm install --omit=dev

# Belt-and-suspenders: even with the version pinned exactly to match this
# base image's tag, explicitly (re)install the matching browser binary so a
# future version bump in package.json can't silently break this again.
RUN npx playwright install --with-deps chromium

COPY server.js ./

ENV PORT=3000
EXPOSE 3000

CMD ["node", "server.js"]
