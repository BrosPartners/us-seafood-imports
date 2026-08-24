"""Tests for chart-colour assignment and chart-lifecycle fixes in assets/app.js.

There is no JS test framework in this repo (and none may be added), so these
tests drive the *actual* app.js code from Python via Node (already present on
the system, not a new dependency): app.js exports a few pure functions plus
`state`/`renderShareChart` for exactly this purpose (see the `module.exports`
guard at the bottom of app.js, which is a no-op in the browser).

Nothing here reimplements the colour-assignment or chart-lifecycle logic —
each test calls the real function from app.js and only asserts on the result.
"""
import json
import shutil
import subprocess
import tempfile
import textwrap
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
APP_JS = ROOT / "assets" / "app.js"
DASHBOARD_JSON = ROOT / "data" / "dashboard.json"

NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(NODE is None, reason="node not available on PATH")


def run_node(script: str):
    """Run a Node script (written to a temp file, since the real
    dashboard.json embedded inline can exceed Windows' command-line length
    limit) and return its parsed JSON stdout."""
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False,
                                      dir=str(ROOT / "tests"),
                                      encoding="utf-8") as f:
        f.write(script)
        script_path = f.name
    try:
        result = subprocess.run([NODE, script_path], capture_output=True, text=True,
                                cwd=str(ROOT))
        if result.returncode != 0:
            raise AssertionError(f"node script failed:\n{result.stderr}")
        return json.loads(result.stdout)
    finally:
        Path(script_path).unlink(missing_ok=True)


def load_real_groups():
    data = json.loads(DASHBOARD_JSON.read_text(encoding="utf-8"))
    return data["groups"]


def test_every_real_group_gets_distinct_series_colours():
    """For every group in the real dashboard.json, the colours
    assignCountryColors() hands back for that group's countries must all be
    distinct (Other included, since Other gets its own fixed colour)."""
    groups = load_real_groups()
    script = textwrap.dedent(f"""
        const app = require({json.dumps(str(APP_JS))});
        const groups = {json.dumps(groups)};
        const out = {{}};
        for (const g of groups) {{
          const names = g.countries.map(c => c.name);
          out[g.key] = app.assignCountryColors(names);
        }}
        console.log(JSON.stringify(out));
    """)
    colours_by_group = run_node(script)

    for group in groups:
        key = group["key"]
        colours = colours_by_group[key]
        assert len(colours) == len(set(colours)), (
            f"group '{key}' has duplicate series colours: {colours} "
            f"for countries {[c['name'] for c in group['countries']]}"
        )


def test_other_always_gets_the_fixed_muted_colour_never_a_palette_slot():
    groups = load_real_groups()
    script = textwrap.dedent(f"""
        const app = require({json.dumps(str(APP_JS))});
        const groups = {json.dumps(groups)};
        const out = {{}};
        for (const g of groups) {{
          const names = g.countries.map(c => c.name);
          out[g.key] = app.assignCountryColors(names);
        }}
        console.log(JSON.stringify({{ colours: out, otherColor: app.OTHER_COLOR,
                                       countryColors: app.COUNTRY_COLORS }}));
    """)
    result = run_node(script)
    other_color = result["otherColor"]
    country_colors = set(result["countryColors"])
    assert other_color not in country_colors

    for group in groups:
        colours = result["colours"][group["key"]]
        for country, colour in zip(group["countries"], colours):
            if country["name"] == "Other":
                assert colour == other_color
            else:
                assert colour != other_color


def test_asp_chart_total_line_never_collides_with_a_country_colour():
    """The 'Toàn nhóm' total line uses TOTAL_COLOR; it must never equal any
    colour handed to a named country, for any real group (this is exactly
    what used to wrap around and collide on Cod/Pollock)."""
    groups = load_real_groups()
    script = textwrap.dedent(f"""
        const app = require({json.dumps(str(APP_JS))});
        const groups = {json.dumps(groups)};
        const out = {{}};
        for (const g of groups) {{
          const names = g.countries.map(c => c.name);
          out[g.key] = app.assignCountryColors(names);
        }}
        console.log(JSON.stringify({{ colours: out, total: app.TOTAL_COLOR }}));
    """)
    result = run_node(script)
    total_color = result["total"]

    for group in groups:
        colours = result["colours"][group["key"]]
        for country, colour in zip(group["countries"], colours):
            if country["name"] != "Other":
                assert colour != total_color, (
                    f"group '{group['key']}': country '{country['name']}' "
                    f"colour collides with the total-line colour {total_color}"
                )


def _node_harness_for_share_chart():
    """A minimal DOM/Chart.js stub so the *real* renderShareChart from
    app.js can run under plain Node and we can observe whether it destroys
    a stale chart instance. No jsdom/library involved — just plain object
    stubs for the handful of things app.js touches."""
    return textwrap.dedent(f"""
        const elements = {{
          "share-card": {{ hidden: false }},
          "chart-share": {{ getContext: () => ({{}}) }},
        }};
        global.document = {{ getElementById: (id) => elements[id] }};
        global.getComputedStyle = () => ({{ getPropertyValue: () => "#000000" }});

        let destroyCount = 0;
        let instanceCount = 0;
        global.Chart = function (ctx, cfg) {{
          instanceCount += 1;
          this.destroyed = false;
          this.destroy = () => {{ this.destroyed = true; destroyCount += 1; }};
        }};

        const app = require({json.dumps(str(APP_JS))});
        app.state.data = {{
          months: ["2026-01"],
          groups: [
            {{ key: "salmon", label: "Salmon", countries: [], volume: [1], asp: [1] }},
            {{ key: "cod", label: "Cod",
               countries: [{{ name: "CHINA", volume: [1], asp: [1] }}],
               volume: [1], asp: [1] }},
          ],
        }};
    """)


def test_switching_to_a_group_with_no_countries_destroys_the_stale_share_chart():
    script = _node_harness_for_share_chart() + textwrap.dedent("""
        // Render Cod first: creates the chart-share instance.
        app.state.activeKey = "cod";
        app.renderShareChart();
        const firstChart = app.state.charts["chart-share"];
        const wasDestroyedBeforeSwitch = firstChart.destroyed;

        // Switch to Salmon (no countries): must hide the card AND destroy
        // the previously created chart, clearing it from state.charts.
        app.state.activeKey = "salmon";
        app.renderShareChart();

        console.log(JSON.stringify({
          wasDestroyedBeforeSwitch,
          firstChartDestroyedAfterSwitch: firstChart.destroyed,
          chartSlotClearedAfterSwitch: app.state.charts["chart-share"] === undefined,
          cardHiddenAfterSwitch: elements["share-card"].hidden,
        }));
    """)
    result = run_node(script)
    assert result["wasDestroyedBeforeSwitch"] is False
    assert result["firstChartDestroyedAfterSwitch"] is True
    assert result["chartSlotClearedAfterSwitch"] is True
    assert result["cardHiddenAfterSwitch"] is True


def test_switching_back_to_a_group_with_countries_renders_a_fresh_chart():
    script = _node_harness_for_share_chart() + textwrap.dedent("""
        app.state.activeKey = "cod";
        app.renderShareChart();
        const firstChart = app.state.charts["chart-share"];

        app.state.activeKey = "salmon";
        app.renderShareChart();

        app.state.activeKey = "cod";
        app.renderShareChart();
        const secondChart = app.state.charts["chart-share"];

        console.log(JSON.stringify({
          gotAFreshInstance: secondChart !== undefined && secondChart !== firstChart,
          freshInstanceNotDestroyed: secondChart.destroyed === false,
          cardVisibleAgain: elements["share-card"].hidden === false,
        }));
    """)
    result = run_node(script)
    assert result["gotAFreshInstance"] is True
    assert result["freshInstanceNotDestroyed"] is True
    assert result["cardVisibleAgain"] is True
