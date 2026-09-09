FROM node:22-bookworm-slim AS client
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY app ./app
COPY components ./components
COPY hooks ./hooks
COPY lib ./lib
COPY public ./public
COPY .openai ./.openai
COPY vite.config.ts next.config.ts tsconfig.json ./
RUN npm run build

FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt requirements.lock ./
RUN pip install --no-cache-dir -r requirements.lock && useradd --create-home --uid 10001 sheetwise
COPY backend ./backend
COPY docs/openapi.yaml ./docs/openapi.yaml
COPY --from=client /app/dist/client ./dist/client
RUN mkdir /app/data && chown -R sheetwise:sheetwise /app
USER sheetwise
ENV APP_HOST=0.0.0.0 PORT=8000 DATA_DIR=/app/data PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["python", "-m", "backend"]
