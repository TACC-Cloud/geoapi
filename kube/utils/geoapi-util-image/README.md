# Geoapi utility image

Docker [image](https://hub.docker.com/r/taccaci/geoapi-util) for utility work on staging/deployment environments of geoapi

This is used for such things as troubleshooting and nightly backups

```
docker build -t taccaci/geoapi-util .
docker push taccaci/geoapi-util:latest
```

```docker run --rm -it taccaci/geoapi-util bash```
