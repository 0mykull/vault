FROM python:3.9-slim-buster

WORKDIR /vault

COPY requirements.txt ./
RUN pip3 install --no-cache-dir -r requirements.txt

COPY . .

ENV FLASK_APP=app
CMD ["python3", "-m", "flask", "run", "--host=0.0.0.0"]

EXPOSE 5000
