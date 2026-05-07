# DialTone Outreach — Lambda container image
#
# Built from the AWS-maintained Python 3.12 Lambda base image so the
# runtime, OS libs, and the Lambda Runtime Interface Client are all
# pre-installed. The image entrypoint is ``lambda_handler.handler``;
# EventBridge schedules pick the task via the event payload (see
# ``lambda_handler.py`` for the supported tasks).
#
# Build / push: see ``deploy/build_and_push.sh``.
FROM public.ecr.aws/lambda/python:3.12

# Install Python deps into the Lambda task root so they sit on
# ``sys.path`` without an extra layer.
COPY requirements.txt ${LAMBDA_TASK_ROOT}/
RUN pip install --no-cache-dir -r ${LAMBDA_TASK_ROOT}/requirements.txt

# Copy application code. ``.dockerignore`` keeps tests, .git, the venv,
# and local CSV exports out of the image.
COPY lambda_handler.py ${LAMBDA_TASK_ROOT}/
COPY outreach/        ${LAMBDA_TASK_ROOT}/outreach/
COPY scripts/         ${LAMBDA_TASK_ROOT}/scripts/

CMD ["lambda_handler.handler"]
