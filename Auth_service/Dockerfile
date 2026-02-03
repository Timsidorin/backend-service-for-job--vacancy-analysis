FROM python:3.10:alpine


WORKDIR /Auth_service


COPY ./requirements.txt /Auth_service/requirements.txt


RUN pip install --no-cache-dir --upgrade -r /Auth_service/requirements.txt


COPY ./app /Auth_service/app

CMD ["python", "main.py"]