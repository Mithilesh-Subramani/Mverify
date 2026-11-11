# RHEL installation

For Mverify 0.16.0, follow [DEPLOYMENT_v0.16.0.md](DEPLOYMENT_v0.16.0.md). It contains separate Mcore and Mverify virtual environment setup, host-local configuration, migrations, update/rollback steps, remote validation and diagnostics.

The engineering deployment runs on RHEL with Ollama and proprietary RTL kept on that host. This repository contains synthetic fixtures only. Mcore binds to loopback; do not expose Mcore or Ollama publicly.
