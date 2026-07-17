# Installation Guide

SC-EVM is packaged as a standard Python package. It requires Python >= 3.11.

## Prerequisite: uv Package Manager
We recommend using `uv` to manage dependencies.
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

## Clone and Install
```bash
git clone git@github.com:roshithrg147/ephemeral-engine.git
cd ephemeral-engine
uv sync
cp .env.example .env
```

For the optional desktop clipboard application:

```bash
uv sync --extra clipboard
```
