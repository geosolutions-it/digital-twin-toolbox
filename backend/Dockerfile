FROM tiangolo/uvicorn-gunicorn-fastapi:python3.10

WORKDIR /app/

SHELL ["/bin/bash", "-c"]

# Install dot net libraries
RUN apt-get update -y && apt-get upgrade -y && apt-get install --no-install-recommends -y wget git && \
    wget https://packages.microsoft.com/config/debian/12/packages-microsoft-prod.deb -O packages-microsoft-prod.deb && \
    dpkg -i packages-microsoft-prod.deb && \
    rm packages-microsoft-prod.deb && \
    apt update && apt install -y apt-transport-https && \
    apt install -y dotnet-sdk-6.0 && \
    apt-get install -y aspnetcore-runtime-6.0 && \
    apt-get install -y dotnet-runtime-6.0 && \
    dotnet tool install -g dotnet-serve --version 1.10.172

ENV PATH="${PATH}:/root/.dotnet/tools"

# POSTGRES_PASSWORD must be included in the env variable for pg2b3dm
RUN dotnet tool install -g i3dm.export --version 2.6.0 && \
    dotnet tool install -g pg2b3dm --version 1.8.4

ARG DDT_ENV=ddt

# Install PDAL
RUN cd / && \
    curl -Ls https://micro.mamba.pm/api/micromamba/linux-64/latest | tar -xvj bin/micromamba && \
    ./bin/micromamba shell init -s bash -p ~/micromamba && \
    source ~/.bashrc && \
    micromamba config append channels conda-forge && \
    micromamba create -n $DDT_ENV python=3.10.13 -y && \
    micromamba install -n $DDT_ENV -c conda-forge pdal=2.6.3 -y

RUN micromamba install -n $DDT_ENV -c conda-forge poetry

# Copy poetry.lock* in case it doesn't exist in the repo
COPY ./pyproject.toml ./poetry.lock* /app/

# Allow installing dev dependencies to run tests
ARG INSTALL_DEV=false
RUN bash -c "if [ $INSTALL_DEV == 'true' ] ; then micromamba run -n $DDT_ENV poetry install --no-root ; else micromamba run -n $DDT_ENV poetry install --no-root --only main ; fi"

# Install gdal python
RUN micromamba run -n $DDT_ENV pip install gdal=="$(micromamba run -n ${DDT_ENV} gdal-config --version).*" --no-build-isolation

ENV PYTHONPATH=/app

COPY ./scripts/ /app/

COPY ./alembic.ini /app/

COPY ./prestart.sh /app/

COPY ./tests-start.sh /app/

COPY ./app /app/app

COPY ./node/ /app/node/

RUN mv /app/celery-reload.sh /celery-reload.sh && \
    mv /app/celery.sh /celery.sh

# Install node
ARG NODE_VERSION=20.11.1

RUN wget -qO- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash

ENV NVM_DIR=/root/.nvm

RUN . "$NVM_DIR/nvm.sh" && nvm install ${NODE_VERSION} && \
    . "$NVM_DIR/nvm.sh" && nvm use v${NODE_VERSION} && \
    . "$NVM_DIR/nvm.sh" && nvm alias default v${NODE_VERSION}

ENV PATH="/root/.nvm/versions/node/v${NODE_VERSION}/bin/:${PATH}"

RUN npm install -g nodemon && \
    cd /app/node/ && \
    npm install

# Activate micromamba enviroment as the default one
RUN echo "micromamba activate ${DDT_ENV}" >> ~/.bashrc

ENV PATH="/root/micromamba/envs/${DDT_ENV}/bin:${PATH}"

ENTRYPOINT ["bash", "-l", "-c"]
