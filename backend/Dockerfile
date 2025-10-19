FROM python:3.11-slim
WORKDIR /backend
COPY . ./backend
RUN pip install --no-cache-dir -r backend/requirements.txt
CMD ["fastapi", "run", "backend/app/main.py", "--port", "8000"]
