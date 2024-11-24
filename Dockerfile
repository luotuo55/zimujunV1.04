# 字幕君 V1.03
FROM python:3.8-slim

# 添加版本标签
LABEL version="1.03" \
      description="字幕君 - 视频字幕生成工具" \
      maintainer="dingguoping55"

# 设置工作目录
WORKDIR /app

# 切换到root用户安装依赖
USER root

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    ffmpeg \
    gcc \
    python3-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# 复制requirements.txt
COPY requirements.txt .

# 安装Python依赖
RUN pip install -i https://pypi.tuna.tsinghua.edu.cn/simple --upgrade pip && \
    pip install -i https://pypi.tuna.tsinghua.edu.cn/simple wheel setuptools && \
    pip install -i https://pypi.tuna.tsinghua.edu.cn/simple --no-cache-dir -r requirements.txt

# 复制项目文件
COPY . .

# 创建必要的目录并设置权限
RUN mkdir -p uploads subtitles && \
    chmod 777 uploads subtitles

# 暴露端口
EXPOSE 5000

# 设置环境变量
ENV FLASK_APP=main.py
ENV PYTHONUNBUFFERED=1

# 启动应用
CMD ["python", "main.py"] 