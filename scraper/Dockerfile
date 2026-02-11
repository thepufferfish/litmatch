FROM python AS build-stage

RUN pip install --no-cache-dir scrapyd-client

WORKDIR /workdir

COPY . .

RUN scrapyd-deploy --build-egg=bookmarks.egg

# Build the image.

FROM python:alpine

# Install build dependencies, pip packages, then remove build deps and add runtime libs.

COPY requirements.txt .

RUN apk --no-cache add --virtual build-dependencies \
   gcc \
   musl-dev \
   libffi-dev \
   libressl-dev \
   libxml2-dev \
   libxslt-dev \
   postgresql-dev \
 && pip install --no-cache-dir \
   scrapyd \
 && pip install --no-cache-dir -r requirements.txt \
 && apk del build-dependencies \
 && apk add \
   libressl \
   libxml2 \
   libxslt \
   libpq

# Mount two volumes for configuration and runtime.

VOLUME /etc/scrapyd/ /var/lib/scrapyd/

COPY ./scrapyd.conf /etc/scrapyd/

RUN mkdir -p /src/eggs/bookmarks

COPY --from=build-stage /workdir/bookmarks.egg /src/eggs/bookmarks/1.egg

EXPOSE 6800

ENTRYPOINT ["scrapyd", "--pidfile="]
