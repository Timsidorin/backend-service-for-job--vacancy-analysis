FROM python:3.12:alpine


WORKDIR /auth_service


COPY ./requirements.txt /auth_service/requirements.txt


RUN pip install --no-cache-dir --upgrade -r /auth_service/requirements.txt


COPY ./app /Auth_service/app

CMD ["python", "main.py"   ]