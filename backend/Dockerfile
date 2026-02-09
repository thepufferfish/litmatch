FROM python:3.12-slim

WORKDIR /backend

COPY . ./backend

RUN pip install --no-cache-dir -r backend/requirements.txt

RUN chmod +x backend/entrypoint.sh

ENTRYPOINT ["backend/entrypoint.sh"]
CMD ["fastapi", "run", "backend/app/main.py", "--port", "8000"]
