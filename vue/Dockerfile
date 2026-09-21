# 前端镜像：多阶段构建（npm 走 npmmirror 淘宝源 → nginx 托管 + 反代 /api）
# ---- 构建阶段 ----
FROM docker.m.daocloud.io/library/node:20-alpine AS build
WORKDIR /app
RUN npm config set registry https://registry.npmmirror.com
COPY package.json .npmrc ./
RUN npm install --no-audit --no-fund
COPY . .
RUN npm run build
# ---- 运行阶段 ----
FROM docker.m.daocloud.io/library/nginx:alpine
# 移除会卡住的默认启动脚本（10-listen-on-ipv6-by-default.sh 在部分环境会阻塞 nginx 启动）
RUN rm -f /docker-entrypoint.d/10-listen-on-ipv6-by-default.sh
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]