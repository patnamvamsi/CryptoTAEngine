FROM python:3.11

COPY . /CryptoTAEngine

WORKDIR /CryptoTAEngine/app

RUN pip install numpy

# TA-Lib
RUN wget http://prdownloads.sourceforge.net/ta-lib/ta-lib-0.4.0-src.tar.gz && \
  tar -xvzf ta-lib-0.4.0-src.tar.gz && \
  cd ta-lib/ && \
  ./configure --prefix=/usr && \
  make && \
  make install

RUN rm -R ta-lib ta-lib-0.4.0-src.tar.gz

RUN pip3 install -r ../requirements.txt

ENV PYTHONPATH "${PYTHONPATH}:/CyryptoTAEngine"

EXPOSE 8001

CMD ["python","-m","uvicorn","main:app","--host=0.0.0.0","--reload","--port","8001"]


#  build an image using this command: sudo docker build -t cryptotaengineimage:0.1 .
#  run the image using this command: sudo docker run -p 8001:8001 --name taengine cryptotaengineimage:0.1