# For more information, please refer to https://aka.ms/vscode-docker-python
FROM python:3.9.13-slim-buster

# Keeps Python from generating .pyc files in the container
ENV PYTHONDONTWRITEBYTECODE=1

# Turns off buffering for easier container logging
ENV PYTHONUNBUFFERED=1

WORKDIR /blurby
COPY ./app /blurby

# Define volumes
VOLUME /blurby/data/
VOLUME /blurby/data/logs/

# Creates a non-root user with an explicit UID and adds permission to access the /blurby folder
# For more info, please refer to https://aka.ms/vscode-docker-python-configure-containers
RUN adduser -u 5678 --disabled-password --gecos "" appuser && chown -R appuser /blurby

# Add permissions to /data for user appuser
RUN chown -R appuser /blurby/data
USER appuser

# Add /home/appuser/.local/bin to PATH
ENV PATH /home/appuser/.local/bin:$PATH

# Install pip requirements
COPY requirements.txt . 
RUN python -m pip install -r requirements.txt

# During debugging, this entry point will be overridden. For more information, please refer to https://aka.ms/vscode-docker-python-debug
CMD ["python", "main.py"]
