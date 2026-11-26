FROM nginx:alpine
COPY nginx-vigia-http.conf /etc/nginx/conf.d/default.conf
EXPOSE 8000
