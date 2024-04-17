FROM mambaorg/micromamba:latest

USER root

WORKDIR /usr/src/app

ENV DEBIAN_FRONTEND noninteractive
ENV LC_ALL C.UTF-8
ENV LANG C.UTF-8
ENV PATH "$PATH:/bin/3.2/python/bin/"
ENV BLENDER_PATH "/bin/3.2"
ENV BLENDERPIP "/bin/3.2/python/bin/pip3"
ENV BLENDERPY "/bin/3.2/python/bin/python3.10"
ENV HW="CPU"

RUN apt-get update && apt-get upgrade && apt-get install --no-install-recommends -y \
    wget \
    libopenexr-dev \
    bzip2 \
    build-essential \
    zlib1g-dev \
    libxmu-dev \
    libxi-dev \
    libxxf86vm-dev \
    libfontconfig1 \
    libxrender1 \
    libgl1-mesa-glx \
    xz-utils \
    libxkbcommon-dev \
    libegl1 \
    libgl1 \
    libgomp1 \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

RUN wget https://packages.microsoft.com/config/debian/11/packages-microsoft-prod.deb -O packages-microsoft-prod.deb
RUN dpkg -i packages-microsoft-prod.deb
RUN rm packages-microsoft-prod.deb
RUN apt update && apt install -y apt-transport-https
RUN apt install -y dotnet-sdk-6.0
RUN apt-get install -y aspnetcore-runtime-6.0
RUN apt-get install -y dotnet-runtime-6.0
RUN dotnet tool install -g dotnet-serve --version 1.10.172
ENV PATH="${PATH}:/root/.dotnet/tools"
RUN dotnet tool install -g pg2b3dm --version 1.8.4
RUN dotnet tool install -g i3dm.export --version 2.6.0

RUN micromamba config append channels conda-forge

# env for pdal
RUN micromamba create -n pdal_env python=3.10.13 -y
RUN micromamba install -n pdal_env -c conda-forge pdal=2.6.3 -y
# env for other python libraries
RUN micromamba create -n tools_env python=3.10.13 -y
RUN micromamba run -n tools_env -c pip install open3d==0.18.0
RUN micromamba run -n tools_env -c pip install py3dtiles[all]==7.0.0
RUN micromamba run -n tools_env -c pip install laspy[laszip]==2.5.3

RUN wget https://mirrors.dotsrc.org/blender/release/Blender3.6/blender-3.6.0-linux-x64.tar.xz \
    && tar -xvf blender-3.6.0-linux-x64.tar.xz --strip-components=1 -C /bin \
    && rm -rf blender-3.6.0-linux-x64.tar.xz \
    && rm -rf blender-3.6.0-linux-x64.tar.xz

ENV NODE_VERSION=20.11.1
RUN wget -qO- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
ENV NVM_DIR=/root/.nvm
RUN . "$NVM_DIR/nvm.sh" && nvm install ${NODE_VERSION}
RUN . "$NVM_DIR/nvm.sh" && nvm use v${NODE_VERSION}
RUN . "$NVM_DIR/nvm.sh" && nvm alias default v${NODE_VERSION}
ENV PATH="/root/.nvm/versions/node/v${NODE_VERSION}/bin/:${PATH}"
RUN node --version
RUN npm --version

COPY package.json /usr/src/app
RUN npm install

CMD /usr/src/app/start.sh
