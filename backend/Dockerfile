FROM tiangolo/uvicorn-gunicorn-fastapi:python3.11

WORKDIR /app/

SHELL ["/bin/bash", "-c"]

ARG DDT_ENV=ddt
ARG OPENSFM_ENV=opensfm

# Install PDAL
RUN cd / && \
    curl -Ls https://micro.mamba.pm/api/micromamba/linux-64/1.5.10 | tar -xvj bin/micromamba && \
    ./bin/micromamba shell init -s bash -p ~/micromamba && \
    source ~/.bashrc && \
    micromamba config append channels conda-forge && \
    micromamba create -n $DDT_ENV python=3.11 -y && \
    micromamba install -n $DDT_ENV -c conda-forge pdal=2.8.4 -y

# see https://github.com/mapillary/OpenSfM/blob/b761d315beff871c928518f6467ea2509b0855b1/Dockerfile
RUN apt-get update \
    && apt-get install -y \
        git \
        build-essential \
        cmake \
        git \
        curl \
        # OpenSfM dependencies
        libeigen3-dev \
        libopencv-dev \
        libceres-dev \
        # mvs-texturing dependencies
        libpng-dev \
        libjpeg-dev \
        libtbb-dev \
        libtiff-dev \
        ca-certificates \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

RUN mkdir /source/ && \
  cd /source/  && \
  git clone --recursive https://github.com/mapillary/OpenSfM.git && \
  cd /source/OpenSfM/ && \
  git checkout b761d315beff871c928518f6467ea2509b0855b1

RUN cd /source/OpenSfM/ && \
    micromamba create -n $OPENSFM_ENV python=3.8.2 -y && \
    micromamba run -n $OPENSFM_ENV pip install -r requirements.txt && \
    micromamba run -n $OPENSFM_ENV python setup.py build

# use fix from here https://github.com/nmoehrle/mvs-texturing/pull/221
RUN cd / && git clone https://github.com/santerioksanen/mvs-texturing.git \
    && cd mvs-texturing \
    && git checkout "feature/tbb-depend" \
    && mkdir build && cd build \
    && cmake .. \
    && make

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

COPY ../scripts/ /app/scripts/

COPY ./alembic.ini /app/

COPY ./prestart.sh /app/

COPY ./tests-start.sh /app/

COPY ./app /app/app

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

RUN npm install -g nodemon

# Install pg2b3dm binaries
RUN cd /bin  && \
    wget https://github.com/Geodan/pg2b3dm/releases/download/v2.19.0/pg2b3dm-linux-x64.zip && \
    unzip ./pg2b3dm-linux-x64.zip && \
    rm -rf ./pg2b3dm-linux-x64.zip

# Install i3dm.export binaries
RUN cd /bin  && \
    wget https://github.com/Geodan/i3dm.export/releases/download/v2.11.0/i3dm.export-linux-x64.zip && \
    unzip ./i3dm.export-linux-x64.zip && \
    rm -rf ./i3dm.export-linux-x64.zip

# Activate micromamba enviroment as the default one
RUN echo "micromamba activate ${DDT_ENV}" >> ~/.bashrc

ENV PATH="/root/micromamba/envs/${DDT_ENV}/bin:${PATH}"

ENTRYPOINT ["bash", "-l", "-c"]
