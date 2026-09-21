# 后端镜像：Python 3.11 + FastAPI
# pip 依赖走阿里云镜像（国内加速）
FROM docker.m.daocloud.io/library/python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple/ \
    PIP_TRUSTED_HOST=mirrors.aliyun.com \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# 先装依赖（利用层缓存）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制源码
COPY . .

EXPOSE 9090

# 上传目录（宿主机通过 compose 挂载持久化，这里兜底创建）
RUN mkdir -p /app/uploads

CMD ["python", "main.py"]