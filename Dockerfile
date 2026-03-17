# Usa Python 3.14 como base
FROM python:3.14-slim

# Variables de entorno
ENV PYTHONUNBUFFERED=1
ENV GH_TOKEN=""
ENV GH_USERNAME=""

# Copia todo lo necesario dentro del contenedor
WORKDIR /app
COPY index.py input.css requirements.txt templates/ ./

# Instala dependencias
RUN pip install --upgrade pip \
    && pip install -r requirements.txt

# Descarga Tailwind CSS
RUN mkdir -p .tailwind \
    && curl -L https://github.com/tailwindlabs/tailwindcss/releases/latest/download/tailwindcss-linux-x64 -o .tailwind/tailwind \
    && chmod +x .tailwind/tailwind

# Comando por defecto al ejecutar la Action
ENTRYPOINT ["python", "index.py"]