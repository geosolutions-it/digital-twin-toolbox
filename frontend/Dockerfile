# Stage 0, "build-stage", based on Node.js, to build and compile the frontend
FROM node:20 AS build-stage

WORKDIR /app

COPY package*.json /app/

RUN npm install

COPY ./ /app/

RUN npm run build

RUN cd /app/mapstore/ && npm install
RUN cd /app/mapstore/ && npm run compile

# Stage 1, based on Nginx, to have only the compiled app, ready for production with Nginx
FROM nginx:1

COPY --from=build-stage /app/dist/ /usr/share/nginx/html
RUN mkdir /usr/share/nginx/html/mapstore/
COPY --from=build-stage /app/mapstore/dist/ /usr/share/nginx/html/mapstore

COPY ./nginx.conf /etc/nginx/conf.d/default.conf
COPY ./nginx-backend-not-found.conf /etc/nginx/extra-conf.d/backend-not-found.conf
COPY env.sh /docker-entrypoint.d/env.sh
RUN chmod +x /docker-entrypoint.d/env.sh
