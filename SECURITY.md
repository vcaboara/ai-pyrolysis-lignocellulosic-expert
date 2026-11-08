# Security Policy & Findings

## Overview

This project implements a comprehensive DevSecOps pipeline to automatically detect vulnerabilities in code, dependencies, and container images. This document describes our security approach, findings, and remediation strategy.

## Base Image: python:3.13-slim (Selected: Option 3)

### Decision Rationale

We use `python:3.13-slim` based on Debian 13.7 as our base image. This decision prioritizes:

1. **Maintainability**: Familiar Debian ecosystem with extensive documentation and library support
2. **Learning**: Allows understanding of real-world security tradeoffs without introducing Alpine complexity (musl vs glibc)
3. **Pragmatism**: For a development/AI tool, Slim's larger attack surface is acceptable given monitoring via automated scanning

### Alternative Options Considered

| Option                  | Image                          | Size     | Vulnerabilities  | Trade-offs                        |
| ----------------------- | ------------------------------ | -------- | ---------------- | --------------------------------- |
| 1 - Alpine              | `python:3.13-alpine`           | ~180MB   | Fewer            | Requires musl, different behavior |
| 2 - Distroless          | `gcr.io/distroless/python3.13` | ~150MB   | Minimal          | No shell, difficult to debug      |
| **3 - Slim (SELECTED)** | `python:3.13-slim`             | ~400MB   | 58 HIGH/CRITICAL | Well-known, good library support  |
| 4 - Custom Minimal      | Custom slim + removals         | Variable | Variable         | Time-intensive, fragile           |

## Vulnerability Findings

### Trivy Container Image Scan Results

**Scan Date**: 2026-11-06  
**Tool**: Trivy v0.76.2  
**Total HIGH/CRITICAL Vulnerabilities**: 58

#### Summary by Package

- **util-linux** (4 CVEs): CVE-2026-76642, CVE-2026-78408, CVE-2026-78409, CVE-2026-78410
- **libexpat1** (4 CVEs): CVE-2026-113351, CVE-2026-115506, CVE-2026-117610, CVE-2026-118370
- **curl** (2 CVEs): CVE-2026-12064, CVE-2026-8458
- **libacl1** (1 CVE): CVE-2026-54369
- **Plus 47 more** across libgcrypt20, libgmp10, libcap2, libpam0g, libssl3, openssh-client, etc.

See [results/TRIVY_FINDINGS_SUMMARY.md](results/TRIVY_FINDINGS_SUMMARY.md) for detailed vulnerability list.

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

We acknowledge and accept the 58 HIGH/CRITICAL vulnerabilities in the Debian base image because:

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

- Python 3.13-slim patches applied via upstream updates
- Subscribe to Debian security advisories for libssl3, openssh-client, curl, expat
- Rebuild image monthly or on critical CVE announcements
- Test Alpine/Distroless alternatives if Debian vulnerabilities increase significantly

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

1. **Immediately switch to Alpine** (Option 1)
   - Reduce attack surface from 58 to ~10 vulnerabilities
   - Trade-off: Test library compatibility with musl

2. **Or use Distroless** (Option 2)
   - Maximum hardening: no shell, no package manager
   - Trade-off: Harder to debug, limited OS tools

3. **Implement WAF/IDS** if exposed to untrusted input

4. **Runtime scanning** with Falco or similar

## Future Work

- [ ] Create `ACCEPTED_RISKS.md` documenting known unfixed vulnerabilities
- [ ] Set up GitHub Actions alerts for new CVEs in base image
- [ ] Evaluate commercial image scanning (e.g., Snyk, Anchore)
- [ ] Performance testing: Alpine vs Slim cold start time
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
