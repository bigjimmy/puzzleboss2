# Puzzleboss 2000

Puzzle hunt management system: round/puzzle tracker, solver coordination, Google Sheets / Discord integration, and an activity-tracking bot. Built by this team for the [MIT Mystery Hunt](https://www.mit.edu/~puzzle/) and similar events.

**Owner**: Benjamin O'Connor (benoc@alum.mit.edu)

## Quick start

```bash
docker-compose up --build
```

Then visit <http://localhost?assumedid=testuser>.

See [docker/README.md](docker/README.md) for the full local-development guide.

## Documentation map

Pick the doc that matches what you're trying to do:

| If you are… | Read |
|---|---|
| A new team setting up Puzzleboss for your hunt | [docs/SETUP.md](docs/SETUP.md) |
| Taking over as admin for an existing team | [docs/OPERATIONS.md](docs/OPERATIONS.md) |
| Trying to fix a broken system **right now** | [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) |
| Developing on Puzzleboss (architecture, conventions) | [CLAUDE.md](CLAUDE.md) |
| Working with Docker locally | [docker/README.md](docker/README.md) |
| Working on the Apps Script add-on | [docs/apps-script-deployment.md](docs/apps-script-deployment.md) |

Companion repo: [puzzleboss2-infra](https://github.com/bigjimmy/puzzleboss2-infra) — Terraform, Grafana dashboards, production operations runbook.

## License & contributions

Contributions welcome via PR. No formal license declared — ask the owner if you intend to use this outside a puzzle-hunt context.
