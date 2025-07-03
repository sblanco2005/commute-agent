FROM python:3.11

WORKDIR /app
COPY . .

RUN pip install --no-cache-dir -r requirements.txt

# If using Playwright
RUN apt-get update && apt-get install -y wget gnupg libnss3 libatk-bridge2.0-0 libgtk-3-0 libxss1 libasound2 libxshmfence1 libgbm1 libxrandr2 libglu1-mesa && \
    pip install playwright && \
    playwright install --with-deps

RUN apt-get update && apt-get install -y tzdata

LABEL rebuild="force"

EXPOSE 8080
CMD ["uvicorn", "api.server:app", "--host", "0.0.0.0", "--port", "8080"]