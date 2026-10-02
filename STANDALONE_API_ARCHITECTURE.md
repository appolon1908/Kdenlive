# Kdenlive Standalone Social Media Video API

## Mission

Turn this repository into an independent, headless-capable video editing and rendering service focused on social-media production.

Kdenlive remains usable as a desktop editor, but automation must not depend on driving the GUI. The service layer should expose stable APIs that can be called by web apps, agents, Middleware, or other systems.

## Standalone rule

This repository must run without Natron, without the Codestra Middleware, and without any social publisher.

It owns its own:
- REST API and OpenAPI contract
- worker/job execution
- PostgreSQL persistence
- Redis/queue integration
- object/artifact storage
- authentication/service authorization
- health/readiness endpoints
- logs, metrics, tracing
- Docker/runtime configuration
- tests and CI

No shared database and no direct source-code dependency on Natron.

## Core responsibility

Kdenlive is the video editing engine:
- timeline creation and editing
- clip assembly and trimming
- audio editing
- automatic captions
- silence removal
- scene/highlight extraction
- automatic social-media reframing
- logo and brand placement
- thumbnail generation
- multi-format exports
- final encoding/rendering
- social-media variants

The headless execution path should be built around Kdenlive/MLT project data, MLT/melt rendering, and FFmpeg/ffprobe where appropriate instead of GUI automation.

## API surface

Minimum v1 contract:

- GET /healthz
- GET /readyz
- GET /v1/capabilities
- POST /v1/assets
- GET /v1/assets/{id}
- POST /v1/projects
- GET /v1/projects/{id}
- POST /v1/timelines
- POST /v1/ai/edit
- POST /v1/ai/highlights
- POST /v1/captions
- POST /v1/reframe
- POST /v1/variants
- POST /v1/renders
- GET /v1/jobs/{id}
- POST /v1/jobs/{id}/cancel
- GET /v1/artifacts/{id}

Long-running work returns a job ID. Rendering must never block an HTTP request until completion.

## AI Media Director

AI must translate natural-language editing intent into validated structured commands, not unrestricted shell commands.

Target capabilities:
- transcription
- subtitle timing and formatting
- scene detection
- highlight extraction
- silence/pause removal
- smart crop and face/object centering
- beat-aware cuts
- hook/intro suggestions
- thumbnail selection
- title/caption/description generation
- social variant creation
- brand-template enforcement

All generated edit plans must be schema validated before execution.

## Social-media profile registry

Keep platform output requirements outside rendering code.

Suggested structure:

profiles/
- youtube-long.yaml
- youtube-short.yaml
- instagram-reel.yaml
- instagram-feed.yaml
- facebook-reel.yaml
- tiktok.yaml
- x-video.yaml
- linkedin-video.yaml

Profiles should define:
- aspect ratio
- width/height
- frame rate
- codec/audio codec
- bitrate or quality target
- caption defaults
- safe zones
- logo/branding rules
- intro/outro rules
- maximum duration policy
- quality-control requirements

## Quality certification

Every completed render should pass automated validation before becoming READY:

1. render completed
2. ffprobe/metadata inspection
3. resolution/aspect-ratio check
4. codec check
5. duration check
6. audio/loudness check
7. black/frozen-frame checks where enabled
8. caption validation
9. safe-zone/branding validation where enabled
10. artifact checksum
11. status = READY

Failed certification must return a machine-readable reason.

## Events

Emit events such as:
- job.accepted
- job.started
- job.progress
- job.completed
- job.failed
- artifact.ready
- render.certified

Support webhooks and/or WebSocket event delivery without making either mandatory for core operation.

## Optional integration

External orchestration may call Kdenlive after Natron produces a VFX artifact, but Kdenlive must treat that result as a normal media asset.

Example:
AI/Client -> Natron (optional VFX) -> Kdenlive -> QC -> Social Publisher

Kdenlive must also support:
AI/Client -> Kdenlive -> QC

## Repository implementation layout

Target layout:

api/
  routes/
  schemas/
  auth/
engine/
ai/
workers/
jobs/
templates/
profiles/
storage/
database/
events/
openapi/
tests/
docker/
Dockerfile
docker-compose.yml
AGENTS.md

## Environment branches

- main: protected stable source authority; no direct implementation pushes
- development: active integration and feature implementation
- testing: promoted candidates for automated/integration testing
- staging: release candidates that passed testing and are ready for staging validation
- production: production-qualified release state only

Promotion direction:

development -> testing -> staging -> production

Production effects and external publishing remain default-deny until explicitly enabled and certified.

## Initial implementation milestones

1. API skeleton + OpenAPI + health/readiness
2. durable job model + queue + worker
3. asset storage
4. headless render adapter
5. render/status/cancel APIs
6. social profile registry
7. QC pipeline
8. captions/transcription
9. AI structured edit planner
10. social variants
11. webhook/WebSocket events
12. Docker + CI + integration tests
