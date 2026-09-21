# Mock 大模型服务镜像（测试沙箱专用）
# 纯标准库实现，构建时无需 pip / 无需联网拉依赖，秒级构建
FROM docker.m.daocloud.io/library/python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    TZ=Asia/Shanghai

WORKDIR /app
COPY server.py .

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=5s --retries=10 --start-period=3s \
    CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/health',timeout=3)"

CMD ["python", "server.py"]
