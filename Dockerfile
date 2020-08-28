FROM python:3.7

ENV PYTHONUNBUFFERED 1
RUN mkdir /ebag

WORKDIR /ebag
COPY . /ebag/

RUN pip3 install -r requirements.txt

CMD [ "gunicorn", "-c", "config/gunicorn/conf.py", "--bind", ":8000", "--chdir", "eshop", "eshop.wsgi:application"]