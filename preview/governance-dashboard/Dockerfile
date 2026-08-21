FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY index.html /usr/share/nginx/html/index.html
COPY styles.css /usr/share/nginx/html/styles.css
COPY app.js /usr/share/nginx/html/app.js
COPY finops.css /usr/share/nginx/html/finops.css
COPY finops.js /usr/share/nginx/html/finops.js
COPY theme-red.css /usr/share/nginx/html/theme-red.css
EXPOSE 8080
