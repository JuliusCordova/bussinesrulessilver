FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY index.html /usr/share/nginx/html/index.html
COPY styles.css /usr/share/nginx/html/styles.css
COPY app.js /usr/share/nginx/html/app.js
COPY finops.css /usr/share/nginx/html/finops.css
COPY finops.js /usr/share/nginx/html/finops.js
COPY theme-red.css /usr/share/nginx/html/theme-red.css
COPY spa.css /usr/share/nginx/html/spa.css
COPY product-polish.css /usr/share/nginx/html/product-polish.css
COPY router.js /usr/share/nginx/html/router.js
COPY finops-polish.js /usr/share/nginx/html/finops-polish.js
COPY quality.js /usr/share/nginx/html/quality.js
COPY quality.css /usr/share/nginx/html/quality.css
EXPOSE 8080
