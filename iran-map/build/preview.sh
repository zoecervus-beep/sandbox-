#!/bin/sh
# Wrap index.html in the publish skeleton for local preview; swap CDN URLs for locally vendored copies.
cd /home/user/sandbox-/iran-map
{ printf '<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><style>:root{color-scheme:light}body{margin:0}[hidden]{display:none!important}</style></head><body>'; cat index.html; printf '</body></html>'; } \
 | sed -e 's|https://cdnjs.cloudflare.com/ajax/libs/d3/7.9.0/d3.min.js|/vendor/d3.min.js|' \
       -e 's|https://cdnjs.cloudflare.com/ajax/libs/topojson/3.0.2/topojson.min.js|/vendor/topojson.min.js|' \
       -e 's|<link rel="stylesheet" href="https://fonts.googleapis.com/css2[^"]*">|<link rel="stylesheet" href="/vendor/fonts.css">|' \
       -e 's|<link rel="preconnect"[^>]*>||g' > preview.html
