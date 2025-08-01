FROM python:3.12
WORKDIR /app

COPY requirements.txt .
COPY supabase_listener/supabase_listener.py . 

RUN pip install --no-cache-dir -r requirements.txt

CMD ["python", "supabase_listener.py"]