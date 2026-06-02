FROM python:3.13-slim

WORKDIR /app

COPY pyproject.toml requirements.lock.txt ./
RUN pip install --no-cache-dir -r requirements.lock.txt

COPY . .
RUN pip install --no-cache-dir .

CMD ["python3", "-m", "discord_bot_curaga"]
