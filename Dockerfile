FROM python:3.13-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY openfix /app/openfix
COPY vendor /app/vendor
ENV PYTHONPATH=/app PYTHONDONTWRITEBYTECODE=1
CMD ["python", "-m", "openfix.case_sam3"]
