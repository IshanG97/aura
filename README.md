# aura
kick-off repo for MachineTalents X UM Hackathon @ Google
https://lu.ma/ibaiz50k?tk=T4VFxm 


## setup
### 1. run locally

create `.env` file from existing `.env.example` file. Update values in `.env`
```bash
cp .env.example .env
```

set up a dedicated virtual environment to run the service
```bash
# # install uv if you haven't already
# curl -LsSf https://astral.sh/uv/install.sh | sh
# https://docs.astral.sh/uv/getting-started/installation/

uv python install 3.12

uv sync --extra dev
```

activate the environment to run commands without the `uv run` prefix
```bash
source .venv/bin/activate
```

install `pre-commit` git hook scripts
```bash
pre-commit install
```

start the service
```bash
# development
fastapi dev --host 127.0.0.1 --port 8000 app.service.py

# production
uvicorn app.service:app --host 127.0.0.1 --port 8000
```

### 2. run in a Docker container

create `.env.docker` file from existing `.env.example` file. Update values in `.env.docker`
```bash
cp .env.example .env.docker
```

build the Docker image
```bash
docker build -t aura .
```

run the Docker container service
```bash
docker compose up
```