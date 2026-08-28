FROM nginx:1.27-alpine
COPY preview/agent-governance-dashboard/nginx.conf /etc/nginx/conf.d/default.conf
COPY preview/agent-governance-dashboard/index.html /usr/share/nginx/html/index.html
COPY preview/governance-dashboard/styles.css /usr/share/nginx/html/styles.css
COPY preview/agent-governance-dashboard/app.js /usr/share/nginx/html/app.js
EXPOSE 8080
