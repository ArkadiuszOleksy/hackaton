# Używamy oficjalnego, lekkiego obrazu Python 3.12 (zgodnie z założeniami projektu)
FROM python:3.12-slim

# Ustawiamy katalog roboczy wewnątrz kontenera
WORKDIR /app

# Kopiujemy plik z listą bibliotek
COPY requirements.txt .

# Instalujemy biblioteki
RUN pip install --no-cache-dir -r requirements.txt

# Kopiujemy resztę naszego kodu (czyli folder app) do kontenera
COPY ./app ./app

# Nasłuchujemy na porcie 8000
EXPOSE 8000

# Komenda startowa uruchamiająca Gateway
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]