# Official Playwright image already includes Chromium + every OS dependency
# it needs (fonts, codecs, etc). Building this yourself without it is the
# single most common source of "works on my machine" pain with headless
# browsers, so it's worth using even though the image is a few hundred MB.
FROM mcr.microsoft.com/playwright:v1.45.0-jammy

WORKDIR /app

COPY package.json ./
RUN npm install --omit=dev

COPY server.js ./

ENV PORT=3000
EXPOSE 3000

CMD ["node", "server.js"]
