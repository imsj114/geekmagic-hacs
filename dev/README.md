# Local dev Home Assistant

A throwaway Home Assistant in Docker for testing the GeekMagic integration against a real device on your LAN — without touching your production HA.

The integration is **bind-mounted from this repo** (`../custom_components/geekmagic`). So testing a branch or PR is just: check it out, restart the container. No HACS update, no production restart, no merge.

## One-time setup

```bash
docker compose -f dev/docker-compose.yml up -d
```

Open http://localhost:8123, create a throwaway local account (onboarding runs once), then:

1. **Settings → Devices & Services → Add Integration → "GeekMagic Display"**.
2. Enter your device's LAN IP (e.g. `192.168.1.123`). The container reaches it via your host network outbound — no extra config needed.

The instance comes preloaded with test data:

- The **`demo`** integration: fake lights, sensors, climate, media players, weather — enough for any widget/layout.
- A few **`Test *`** template entities (temperature, humidity, battery, power, motion) in `config/configuration.yaml`. `Test Power` / `Test Motion` change every 5s so charts/sparklines build up history.

## Testing a branch or PR

```bash
git checkout some-pr-branch
docker compose -f dev/docker-compose.yml restart   # ~5–10s; reloads the new code
```

Restart is needed because Python module changes aren't hot-reloaded. (Editing only `configuration.yaml` or entity options can use HA's in-app reload instead.)

## Faster loop: no HA, no device

For most widget/layout/theme work you don't need HA at all — the existing scripts render the real pipeline against mock HA data:

```bash
uv run python scripts/generate_samples.py            # write sample PNGs to samples/
uv run python scripts/debug_render.py <device_ip>    # render + upload to a real device
```

Use this local HA when you specifically need to exercise the *integration* — config flow, entities, coordinator, services, the panel.

## Commands

```bash
docker compose -f dev/docker-compose.yml up -d        # start
docker compose -f dev/docker-compose.yml logs -f      # tail logs (geekmagic at debug)
docker compose -f dev/docker-compose.yml restart      # reload code after a branch switch
docker compose -f dev/docker-compose.yml down         # stop (keeps config/)
docker compose -f dev/docker-compose.yml down -v      # stop and wipe HA state
```

To reset HA to a clean slate, delete the generated files in `config/` (everything except `configuration.yaml` and `.gitignore`).
