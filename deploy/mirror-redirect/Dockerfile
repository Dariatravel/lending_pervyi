FROM node:24-alpine@sha256:ec318aabf188af4e5488847eea4b24452650b9917140563e140762526a37f1df
COPY deploy/mirror-redirect/server.cjs deploy/mirror-redirect/vk-return.html /deploy/mirror-redirect/
COPY data/old-site-redirects.json data/retired-redirects.json data/short-links-generated.json data/short-links.json /data/
USER node
ENTRYPOINT ["node", "/deploy/mirror-redirect/server.cjs"]
