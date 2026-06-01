FROM python:3.11-slim

# System deps: JDK for Android SDK, wget/unzip for SDK install, git, Node.js
RUN apt-get update && apt-get install -y \
    openjdk-17-jdk-headless \
    wget \
    unzip \
    git \
    curl \
    ca-certificates \
    gnupg \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Android SDK
ENV ANDROID_SDK_ROOT=/opt/android-sdk
RUN mkdir -p ${ANDROID_SDK_ROOT}/cmdline-tools && \
    wget -q https://dl.google.com/android/repository/commandlinetools-linux-11076708_latest.zip \
         -O /tmp/cmdline-tools.zip && \
    unzip -q /tmp/cmdline-tools.zip -d ${ANDROID_SDK_ROOT}/cmdline-tools && \
    mv ${ANDROID_SDK_ROOT}/cmdline-tools/cmdline-tools \
       ${ANDROID_SDK_ROOT}/cmdline-tools/latest && \
    rm /tmp/cmdline-tools.zip

ENV PATH="${ANDROID_SDK_ROOT}/cmdline-tools/latest/bin:${ANDROID_SDK_ROOT}/platform-tools:${ANDROID_SDK_ROOT}/emulator:${PATH}"

RUN yes | sdkmanager --licenses && \
    sdkmanager "platform-tools" "emulator" "platforms;android-34" \
               "system-images;android-34;google_apis;x86_64"

RUN echo "no" | avdmanager create avd \
    -n mopot_avd \
    -k "system-images;android-34;google_apis;x86_64" \
    --device "pixel_6"

# Flutter
ENV FLUTTER_HOME=/opt/flutter
RUN git clone --depth 1 --branch stable \
    https://github.com/flutter/flutter.git ${FLUTTER_HOME} && \
    ${FLUTTER_HOME}/bin/flutter config --no-analytics && \
    ${FLUTTER_HOME}/bin/flutter doctor --android-licenses || true
ENV PATH="${FLUTTER_HOME}/bin:${PATH}"

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY package.json .
RUN npm install

COPY . .
RUN npm install -g .

EXPOSE 7432

# macOS users: run agents directly on host — emulator requires KVM (Linux only).
# On Linux, add --device /dev/kvm to docker run for hardware acceleration.
CMD ["uvicorn", "webhook.main:app", "--host", "0.0.0.0", "--port", "7432"]
