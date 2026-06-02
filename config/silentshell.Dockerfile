# =============================================================================
# silentshell Dockerfile — pi coding agent
# =============================================================================
# This file was copied into your project by 'silentshell init'. It is yours
# to modify — add system packages, language runtimes, dotfiles, whatever your
# project needs. The sections marked IMPORTANT below must stay consistent with
# your .silentshell.toml.
# =============================================================================

FROM node:22-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    build-essential \
    python3 \
    && rm -rf /var/lib/apt/lists/*

# Install mise (polyglot tool version manager)
RUN curl https://mise.run | MISE_INSTALL_PATH=/usr/local/bin/mise sh

# Install pi coding agent globally
RUN npm install -g @mariozechner/pi-coding-agent

# =============================================================================
# IMPORTANT: the user here must match image_user in your .silentshell.toml.
# The UID/GID are used for tmpfs mounts and volume ownership.
# =============================================================================
RUN useradd -m -s /bin/bash mary && \
    mkdir -p /home/mary/.pi && \
    chown -R mary:mary /home/mary

# Switch to non-root user before installing user-scoped tools
USER mary

# =============================================================================
# IMPORTANT: silentshell mounts your project at /project. Do not change this.
# =============================================================================
WORKDIR /project

# Default command - run pi in interactive mode
CMD ["pi"]
