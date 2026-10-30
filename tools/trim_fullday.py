"""Re-trim a reel city to a FULL service day for the web map.

The reel trims (TransitPulse/data/<city>_gtfs) keep only 06:30-10:00, which
is all a 20-minute reel needs and would leave the web map empty by noon.
This reuses TransitPulse's own trim_city.trim() unchanged - same feed, same
date, same frame - with the time window opened to 00:00-30:00, and writes to
_nosync_data/data/<city>_gtfs so the reel's copies are never touched.

Usage: python trim_fullday.py boston prague rome
"""
import os
import sys

TP_TOOLS = "/Users/milan/Dropbox/Dataprojects/NEW SCIENCE OF MAPS/Youtube/TransitPulse/tools"
sys.path.insert(0, TP_TOOLS)
import trim_city as tc  # noqa: E402

tc.HERE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "_nosync_data")
for key in sys.argv[1:]:
    tc.KEEP_WINDOW[key] = (0.0, 30.0)
    tc.trim(key)
