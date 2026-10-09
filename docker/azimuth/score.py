"""Container entrypoint: read a JSON list of 30-mers on stdin, write scores.

Deliberately dumb. No validation of biology, no fallback, no rounding: it
featurizes and scores through Azimuth and reports exactly what Azimuth returned.
All policy lives in the caller. Output: {"scores": [float, ...]} on success, or
{"error": "..."} with a non-zero exit code.

Azimuth prints progress text to stdout ("No model file specified, ..."), which
would corrupt the JSON, so stdout is pointed at stderr while it runs and the
real stdout is used only for the final JSON document.
"""
import json
import sys

import matplotlib

matplotlib.use("Agg")  # must precede the azimuth import; no display in a container


def main():
    real_stdout = sys.stdout
    sys.stdout = sys.stderr
    try:
        seqs = json.load(sys.stdin)
        import numpy as np
        import azimuth.model_comparison as m

        scores = m.predict(np.array([str(s) for s in seqs]), None, None)
        out = {"scores": [float(x) for x in scores]}
    except Exception as exc:  # report, never fabricate
        real_stdout.write(json.dumps({"error": "%s: %s" % (type(exc).__name__, exc)}))
        sys.exit(1)
    real_stdout.write(json.dumps(out))


main()
