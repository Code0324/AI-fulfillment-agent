import sys
import logging
from jobs.demo_guest_checkout_fulfillment import main

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("demo_runner")

print("STARTING DEMO", flush=True)
try:
    main()
    print("DEMO FINISHED, exit code: 0", flush=True)
except SystemExit as e:
    print(f"DEMO FINISHED, exit code: {e.code}", flush=True)
except Exception as e:
    logging.exception("DEMO CRASHED")
    print(f"DEMO CRASHED: {type(e).__name__}: {e}", flush=True)
    raise
