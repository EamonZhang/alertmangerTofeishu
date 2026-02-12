FROM python:3.13.6-alpine3.21

WORKDIR /app

COPY alertmanager_feishu_webhook.py .

RUN pip install --no-cache-dir flask requests gunicorn tenacity

EXPOSE 9527

CMD ["gunicorn", "-b", "0.0.0.0:9527", "-w", "2", "alertmanager_feishu_webhook:feishu"]
