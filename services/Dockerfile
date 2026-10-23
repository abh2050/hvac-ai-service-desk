# One image for every Python Lambda in the pipeline. Each function sets its own handler (CMD).
# Built for arm64 (Graviton). Build context: the repository root.
FROM public.ecr.aws/lambda/python:3.12-arm64

COPY services/requirements-lambda.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

ENV APP_ROOT=/var/task/app
COPY services/ ${LAMBDA_TASK_ROOT}/
COPY config/ /var/task/app/config/
COPY data/processed/manual_pages.jsonl /var/task/app/data/processed/manual_pages.jsonl
COPY data/deploy/catalog.json /var/task/app/data/deploy/catalog.json
COPY reports/gate-3-detail.json /var/task/app/reports/gate-3-detail.json
COPY pipelines/evaluation/gate4_seed.py /var/task/app/pipelines/evaluation/gate4_seed.py

CMD ["handlers.detect.handler"]
