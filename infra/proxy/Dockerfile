FROM public.ecr.aws/docker/library/node:20-alpine
WORKDIR /app
COPY stream-proxy.js ./stream-proxy.js
RUN npm init -y && npm i node-fetch@3
ENV PORT=8080
EXPOSE 8080
CMD ["node", "stream-proxy.js"]