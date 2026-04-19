# Wybieramy lekką wersję Pythona zgodną ze specyfikacją (3.12) [cite: 58]
FROM python:3.12-slim

# Ustawiamy katalog roboczy wewnątrz kontenera
WORKDIR /app

# Kopiujemy listę zależności i instalujemy je
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Kopiujemy kod aplikacji
COPY ./app ./app

# Eksponujemy port 8000, na którym pracuje Gateway [cite: 58]
EXPOSE 8000

# Komenda startowa - ważne: host musi być 0.0.0.0, aby Docker go widział
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]