FROM node:16-alpine AS node

FROM mambaorg/micromamba:1.5.1-alpine

COPY --from=node /usr/lib /usr/lib
COPY --from=node /usr/local/lib /usr/local/lib
COPY --from=node /usr/local/include /usr/local/include
COPY --from=node /usr/local/bin /usr/local/bin

USER root

WORKDIR /usr/src/app

RUN micromamba config append channels conda-forge

# env for pdal
RUN micromamba create -n pdal_env python=3.10.13 -y
RUN micromamba install -n pdal_env -c conda-forge pdal=2.6.0 -y
# env for other python libraries
RUN micromamba create -n tools_env python=3.10.13 -y
COPY requirements_tools.txt /usr/src/app
RUN micromamba run -n tools_env -c pip install -r requirements_tools.txt

COPY package*.json /usr/src/app
RUN npm install

RUN apk add dotnet6-sdk
RUN dotnet tool install -g dotnet-serve --version 1.10.172
ENV PATH="${PATH}:/root/.dotnet/tools"
RUN dotnet tool install -g pg2b3dm --version 1.8.4
RUN dotnet tool install -g i3dm.export --version 2.6.0

COPY . /usr/src/app

CMD /usr/src/app/start.sh
