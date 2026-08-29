# Builds Synthea from source at a pinned release tag, so generation is
# reproducible: same tag + same seed + same population size always gives
# the same patients. Bump SYNTHEA_VERSION deliberately, not silently.
ARG SYNTHEA_VERSION=v4.0.0

FROM eclipse-temurin:17-jdk AS build
ARG SYNTHEA_VERSION
WORKDIR /build
RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*
RUN git clone --depth 1 --branch ${SYNTHEA_VERSION} \
    https://github.com/synthetichealth/synthea.git .
RUN ./gradlew uberJar --no-daemon

FROM eclipse-temurin:17-jre
WORKDIR /app
COPY --from=build /build/build/libs/synthea-with-dependencies.jar ./synthea.jar

# Synthea writes to ./output relative to the working directory by default,
# so mount a host folder to /app/output at `docker run` time to get the
# generated FHIR bundles out.
ENTRYPOINT ["java", "-jar", "synthea.jar"]
