#!/bin/sh
exec /usr/local/bin/ffmpeg -hide_banner -loglevel warning \
  -fflags nobuffer -rtsp_transport tcp \
  -i rtsp://127.0.0.1:8554/YOUR_RANDOM_STREAM_ID_in \
  -map 0:v:0 -map 0:a:0 -c:v copy -c:a libopus -b:a 128k \
  -application lowdelay -frame_duration 20 \
  -rtsp_transport tcp -f rtsp \
  rtsp://obs-publisher:YOUR_PUBLISH_PASSWORD@127.0.0.1:8554/YOUR_RANDOM_STREAM_ID
