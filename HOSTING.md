# Free public demonstration on Render

The [public replay demo](https://water-diagnostics-demo.onrender.com) is deployed
on Render. Its health, free investigation/download, gap report, both recovery
outcomes and paid-route rejection were checked on October 28, 2026. Evidence is
in `qualification/2026-10-28/public-demo-check.json`.

The repository includes a `render.yaml` Blueprint for one **Free Python web
service**. No database, persistent disk, GPU or model download is required.
This is a review demo, not a production telemetry service. The following steps
also describe how to reproduce the deployment in another Render account.

## Publish

1. Sign in to the [Render dashboard](https://dashboard.render.com/), using GitHub
   if desired. Confirm access to `Sanidhya77/water-diagnostics`.
2. Choose **New → Blueprint**, select that repository and its `main` branch.
3. Review `render.yaml`: one service, `plan: free`. Confirm the displayed price
   is $0 before creating it. Do not add provider keys or paid resources.
4. Deploy. Render installs `requirements-tested.txt`, chooses Python 3.12 from
   `.python-version`, and starts the backend on its assigned port. Its supplied
   `RENDER_EXTERNAL_URL` configures the allowed HTTPS origin.
5. Open the resulting `https://…onrender.com` address. `/health` should return
   `status: ready` and `public_demo: true`.
6. Confirm the Public demo note, two recorded weeks, saved Nemotron report,
   free local checks, Markdown download and both recovery simulations. The fresh
   inference and reference-lookup controls must be disabled. A direct request to
   either paid backend route is also rejected.

If creating a Web Service manually, use Python runtime and Free instance:

```text
Build command: python -m pip install -r requirements-tested.txt
Start command: python -m water_diagnostics serve --host 0.0.0.0 --port $PORT --public-demo
Health check: /health
```

Do not select a static-site service: it cannot execute this Python backend.
The default onrender.com origin is supported; additional domains need explicit
origin configuration and testing.

## Cost and session behavior

Public mode blocks Nebius and Tavily calls on the server, even if a visitor
bypasses the disabled buttons. It does not load provider credentials or use a
resettable spending ledger. Saved results are identified as prior inference.
For a fresh Nebius call, use the local build with your own key and its original
$0.02/run and $5 project guards.

Generated local reports and simulated recovery results are held in bounded
server memory. Download them before the server restarts. No operator data upload,
account storage, live sensor connector or long-term incident database is offered.
Prepared observations and saved reports are restored from the repository.

Render's [free-service limits](https://render.com/docs/free) include sleeping
after 15 idle minutes, a wake-up delay of about a minute, temporary filesystem
contents and workspace usage allowances. With a payment method, some allowance
overages can incur charges; inspect billing/spend controls before publishing.
Do not upgrade resources for this demonstration. Check access before recording
and keep the downloadable source build available if the service is asleep.

Blueprint fields follow [Render's specification](https://render.com/docs/blueprint-spec).
Successful local tests do not prove that a deployment succeeded; record the real
deployment URL and test it after Render reports the service live.
