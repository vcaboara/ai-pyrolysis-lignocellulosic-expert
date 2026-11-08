# Security Policy & Findings

## Overview

This project implements a comprehensive DevSecOps pipeline to automatically detect vulnerabilities in code, dependencies, and container images. This document describes our security approach, findings, and remediation strategy.

## Base Image: python:3.13-alpine (Selected: Option 1)

### Decision Rationale

We use `python:3.13-alpine` as our base image. This decision prioritizes:

1. **Reduced attack surface**: Smaller base image and fewer OS packages by default
2. **Security-first defaults**: Lower baseline vulnerability exposure for local CI/runtime images
3. **Pragmatism**: Works for this project while still allowing reproducible security scanning in CI

### Alternative Options Considered

- **1 - Alpine (SELECTED)**
- Image: `python:3.13-alpine`; size: ~180MB; vulnerabilities: lower baseline; trade-off: musl differences vs glibc.
- **2 - Distroless**
- Image: `gcr.io/distroless/python3-debian12`; size: ~150MB; vulnerabilities: minimal; trade-off: no shell, harder to debug.
- **3 - Slim**
- Image: `python:3.13-slim`; size: ~400MB; vulnerabilities: higher baseline; trade-off: familiar Debian ecosystem, larger footprint.
- **4 - Custom Minimal**
- Image: custom hardened image; size: variable; vulnerabilities: variable; trade-off: time-intensive, higher maintenance overhead.

## Vulnerability Findings

### Trivy Container Image Scan Results

**Scan Date**: Rolling (per CI/local run)
**Tool**: Trivy v0.76.2 (or newer)
**Scope**: `ai-pyrolysis-ligno:runtime` image built from `python:3.13-alpine`

Vulnerability counts vary over time as upstream Alpine and package feeds change.
Do not treat a static number in this document as authoritative; use the latest Trivy output from the current run.

If scan artifacts are generated locally, review `results/TRIVY_FINDINGS_SUMMARY.md` (when present) for that run's details.

### Python Dependency Vulnerabilities

**Status**: ✅ No known vulnerabilities

Checked via `pip-audit` in the CI pipeline. All direct and transitive dependencies have been evaluated.

### Code-Level Vulnerabilities

Checked via:

- **Bandit**: SAST scanner for Python code
- **Privacy Guard**: Secrets/PII detection
- **Ruff**: Linting and safety checks

All pass in current CI pipeline.

## Risk Acceptance

We acknowledge that OS-level vulnerabilities can still appear in Alpine-based images and are managed via continuous scanning because:

1. **Use Case**: This is a development/CI tool, not a production user-facing service
2. **Defense in Depth**: Vulnerabilities are monitored and reported in every CI run
3. **Rapid Response**: Can rebuild image with patched base within hours if critical CVE affects us
4. **Learning Value**: Developers learn security scanning, CVE triage, and remediation workflows

## Mitigation Strategies

### 1. Automated Scanning (CI Integration)

- **On every commit**: Run Trivy container image scan
- **On every push**: Validate dependency vulnerabilities via pip-audit
- **Early warning**: Detect new vulnerabilities in base image automatically
- **No silent failures**: Exit code 1 if HIGH/CRITICAL vulnerabilities found

### 2. Monitoring

- Trivy scan results saved to `results/TRIVY_FINDINGS_SUMMARY.md`
- Historical tracking of vulnerability counts over time
- Baseline comparison when upgrading base image

### 3. Upgrade Strategy

- Track `python:3.13-alpine` upstream updates and rebuild regularly
- Subscribe to Alpine security advisories and Trivy database updates
- Rebuild image monthly or on critical CVE announcements
- Re-evaluate Distroless or further hardening if vulnerability trend worsens

### 4. Incident Response

If a **critical** CVE (CVSS 9.0+) affects a package in our base image:

1. Check if package is actually used by the application
2. If used: Trigger emergency rebuild with Alpine/Distroless
3. If unused: Document in `.dockerignore` and accepted-risks list
4. If exploitable: Emergency patch release

## Security Scanning Tools & Gates

### Order of Execution (run_local_ci.py)

1. **Bandit** - Code SAST scanning
2. **pip-audit** - Python dependency vulnerability scanning
3. **Trivy** - Container image OS/library scanning
4. **Privacy Guard** - Secrets/PII detection
5. **Black** - Code formatter (security updates: CVE fixes)
6. **Ruff** - Linting
7. **mypy** - Type checking
8. **unittest** - Functional tests

### Running Locally

```bash
# All security gates
python run_local_ci.py --security --deps-audit --image-scan

# Individual gates
python run_local_ci.py --deps-audit          # Dependency audit only
python run_local_ci.py --image-scan          # Image scanning only

# Docker compose (all gates)
$env:COMPOSE_FILE = "docker/docker-compose.yml"
docker compose --profile ci up
```

## Recommendations for Production Deployment

If this project moves to production (e.g., as a service):

1. **Keep Alpine and tighten hardening**
   - Pin image digests
   - Reduce installed packages to strict minimum
   - Enforce regular rebuild cadence

2. **Consider Distroless** for maximum hardening
   - No shell/package manager in runtime
   - Trade-off: harder debugging and operational tooling

3. **Implement WAF/IDS** if exposed to untrusted input

4. **Runtime scanning** with Falco or similar

## Future Work

- [ ] Create `ACCEPTED_RISKS.md` documenting known unfixed vulnerabilities
- [ ] Set up GitHub Actions alerts for new CVEs in base image
- [ ] Evaluate commercial image scanning (e.g., Snyk, Anchore)
- [ ] Performance testing: Alpine vs Distroless cold start time
- [ ] Document emergency response procedure for CVSS 9.0+ CVEs

## References

- [Trivy Documentation](https://aquasecurity.github.io/trivy/)
- [pip-audit Documentation](https://github.com/pypa/pip-audit)
- [Bandit Documentation](https://bandit.readthedocs.io/)
- [OWASP Top 10 Vulnerabilities](https://owasp.org/www-project-top-ten/)
- [Docker Base Image Comparison](https://wiki.alpinelinux.org/wiki/Alpine_Linux:Comparison_with_other_distros)

---

**Last Updated**: 2026-11-06  
**Next Review**: 2026-12-06
