#!/usr/bin/env python3
"""Launch the exact three V3 full-grid workers under global supervision."""

import json

from garc_eval.accelerated_event_query.oracle_v3_full_grid_supervisor import (
    launch_supervised_execution,
)


if __name__ == "__main__":
    print(json.dumps(launch_supervised_execution(), indent=2, sort_keys=True))
