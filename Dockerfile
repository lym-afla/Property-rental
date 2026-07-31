# syntax=docker/dockerfile:1.7

FROM node:20-bookworm-slim AS frontend-build
WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN --mount=type=cache,target=/root/.npm npm ci
COPY frontend/index.html frontend/tsconfig.json frontend/tsconfig.app.json frontend/tsconfig.node.json frontend/vite.config.ts ./
COPY frontend/public ./public
COPY frontend/src ./src
RUN npm run build

FROM python:3.11-slim-bookworm AS python-build
ENV UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_LINK_MODE=copy
WORKDIR /build
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    pip install --no-cache-dir uv==0.8.3 && \
    uv sync --frozen --no-dev --no-editable && \
    pip uninstall -y uv

FROM python:3.11-slim-bookworm AS static-build
ENV PATH=/opt/venv/bin:$PATH \
    PYTHONDONTWRITEBYTECODE=1 \
    DJANGO_SETTINGS_MODULE=property_rental.settings.build
WORKDIR /app
COPY --from=python-build /opt/venv /opt/venv
COPY property_rental/manage.py property_rental/gunicorn.conf.py ./
COPY property_rental/property_rental ./property_rental
COPY property_rental/rentals ./rentals
COPY --from=frontend-build /build/property_rental/rentals/static/frontend ./rentals/static/frontend
RUN python manage.py collectstatic --noinput --clear

FROM python:3.11-slim-bookworm AS runtime
ENV PATH=/opt/venv/bin:$PATH \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=property_rental.settings.prod \
    PORT=8000
WORKDIR /app
RUN groupadd --gid 10001 app && useradd --uid 10001 --gid app --no-create-home --shell /usr/sbin/nologin app
COPY --from=python-build /opt/venv /opt/venv
COPY property_rental/manage.py property_rental/gunicorn.conf.py ./
COPY property_rental/property_rental ./property_rental
COPY property_rental/rentals ./rentals
COPY --from=frontend-build /build/property_rental/rentals/static/frontend ./rentals/static/frontend
COPY --from=static-build /app/staticfiles ./staticfiles
RUN find /app -type d \( -name tests -o -name test -o -name e2e -o -name __fixtures__ \) -prune -exec rm -rf '{}' + && \
    find /opt/venv -type d \( -name tests -o -name e2e -o -name __fixtures__ \) -prune -exec rm -rf '{}' + && \
    find /app /opt/venv -type f \( -name '*.sqlite3' -o -name '*.map' -o -name '.env*' \) -delete && \
    chown -R app:app /app
USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD python -c "import sys,urllib.request; request=urllib.request.Request('http://127.0.0.1:'+sys.argv[1]+'/health/live',headers={'X-Forwarded-Proto':'https'}); urllib.request.urlopen(request,timeout=2)" "${PORT:-8000}" || exit 1
CMD ["gunicorn", "--config", "gunicorn.conf.py", "property_rental.wsgi:application"]
