FROM python:3.12
WORKDIR /app


COPY action_server/requirements.txt .
COPY action_server/action_server.py .
COPY app .

RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 5000
EXPOSE 8000 

CMD ["gunicorn", "-b","0.0.0.0:5000","action_server:app"]