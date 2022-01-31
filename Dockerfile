FROM python
WORKDIR /
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .

ENV CELERY_BROKER_URL redis://redis:6379/0
ENV CELERY_RESULT_BACKEND redis://redis:6379/0
ENV HOST 0.0.0.0
ENV PORT 5000
ENV DEBUG true
RUN pip install celery
RUN pip install gunicorn
# CMD ["gunicorn", "--bind", "0.0.0.0:5000", "main:app"]