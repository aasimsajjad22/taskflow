# Development image for the Django app. (A smaller production image comes in Phase 9.)
# Start from the official Python 3.12 image. "slim" = smaller Debian base.
FROM python:3.12-slim
# Don't write .pyc cache files inside the container (we don't need them).
ENV PYTHONDONTWRITEBYTECODE=1
# Send Python output straight to the terminal (no buffering), so logs show instantly.
ENV PYTHONUNBUFFERED=1
# All next commands run inside /app in the container. It's created if missing.
WORKDIR /app
# Copy ONLY the requirement files first.
# Docker caches each step. If requirements don't change, the slow "pip install"
# step below is reused from cache, even if your code changed. Big time saver.
COPY requirements/ requirements/
# Install dev packages (base + tools). --no-cache-dir keeps the image smaller.
RUN pip install --no-cache-dir -r requirements/dev.txt
# Now copy the rest of the project code into /app.
COPY . .
# Document that the app listens on port 8000.
EXPOSE 8000
# Default command when the container starts: the Django dev server.
# 0.0.0.0 = listen on all network interfaces, so your Mac can reach it.
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]