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


def test_is_data_stale_false_when_recent():
    """Đúng kịch bản dữ liệu thật hôm nay: latest_period = 2026-06, hôm nay
    2026-08-24 — cách ngày kết thúc tháng 06 (2026-07-01) 54 ngày, dưới
    ngưỡng 75 ngày, nên KHÔNG được báo cũ."""
    script = textwrap.dedent(f"""
        const app = require({json.dumps(str(APP_JS))});
        const now = new Date(2026, 7, 24); // 2026-08-24
        console.log(JSON.stringify({{
          fresh: app.isDataStale("2026-06", now),
          onThreshold: app.isDataStale("2026-06", new Date(2026, 6, 1 + app.STALENESS_THRESHOLD_DAYS)),
        }}));
    """)
    result = run_node(script)
    assert result["fresh"] is False
    assert result["onThreshold"] is False


def test_is_data_stale_true_when_older_than_threshold():
    script = textwrap.dedent(f"""
        const app = require({json.dumps(str(APP_JS))});
        const now = new Date(2026, 6, 2 + app.STALENESS_THRESHOLD_DAYS); // just past threshold
        console.log(JSON.stringify({{
          stale: app.isDataStale("2026-06", now),
          noPeriod: app.isDataStale(null, now),
        }}));
    """)
    result = run_node(script)
    assert result["stale"] is True
    assert result["noPeriod"] is False


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


def test_find_other_outlier_returns_none_when_no_group_has_countries():
    """Salmon has no country list at all -> no Other -> no outlier."""
    script = textwrap.dedent(f"""
        const app = require({json.dumps(str(APP_JS))});
        const group = {{ countries: [] }};
        console.log(JSON.stringify(app.findOtherOutlier(group, 0)));
    """)
    assert run_node(script) is None


def test_find_other_outlier_returns_none_when_biggest_unlisted_is_smaller_than_smallest_named():
    script = textwrap.dedent(f"""
        const app = require({json.dumps(str(APP_JS))});
        const group = {{
          countries: [
            {{ name: "NORWAY", volume: [100] }},
            {{ name: "CANADA", volume: [200] }},
            {{ name: "Other", volume: [50], top_unlisted: [[
                {{ name: "THAILAND", volume: 40 }} ]] }},
          ],
        }};
        console.log(JSON.stringify(app.findOtherOutlier(group, 0)));
    """)
    assert run_node(script) is None


def test_find_other_outlier_returns_the_unlisted_country_when_it_beats_the_smallest_named():
    script = textwrap.dedent(f"""
        const app = require({json.dumps(str(APP_JS))});
        const group = {{
          countries: [
            {{ name: "NORWAY", volume: [5462] }},
            {{ name: "CANADA", volume: [5410] }},
            {{ name: "Other", volume: [99999], top_unlisted: [[
                {{ name: "THAILAND", volume: 54564 }},
                {{ name: "IRAN", volume: 100 }} ]] }},
          ],
        }};
        console.log(JSON.stringify(app.findOtherOutlier(group, 0)));
    """)
    result = run_node(script)
    assert result == {"name": "THAILAND", "volume": 54564}


def test_find_other_outlier_matches_real_haddock_and_cod_2026_06():
    """Same evidence the brief cites: haddock -> THAILAND, cod -> INDIA."""
    groups = load_real_groups()
    script = textwrap.dedent(f"""
        const app = require({json.dumps(str(APP_JS))});
        const data = {json.dumps(json.loads(DASHBOARD_JSON.read_text(encoding="utf-8")))};
        const months = data.months;
        const i = months.indexOf("2026-06");
        const byKey = Object.fromEntries(data.groups.map(g => [g.key, g]));
        console.log(JSON.stringify({{
          haddock: app.findOtherOutlier(byKey["haddock"], i),
          cod: app.findOtherOutlier(byKey["cod"], i),
        }}));
    """)
    result = run_node(script)
    assert result["haddock"]["name"] == "THAILAND"
    assert result["cod"]["name"] == "INDIA"


def test_share_tooltip_after_body_empty_when_hovered_series_is_not_other():
    script = textwrap.dedent(f"""
        const app = require({json.dumps(str(APP_JS))});
        app.state.data = {{
          groups: [{{ key: "cod", countries: [
            {{ name: "CHINA", volume: [1] }},
            {{ name: "Other", volume: [1], top_unlisted: [[
                {{ name: "INDIA", volume: 59475 }} ]] }},
          ] }}],
        }};
        app.state.activeKey = "cod";
        const items = [{{ dataset: {{ label: "CHINA" }}, dataIndex: 0 }}];
        console.log(JSON.stringify(app.shareTooltipAfterBody(items)));
    """)
    assert run_node(script) == []


def test_share_tooltip_after_body_lists_top_unlisted_when_hovering_other():
    script = textwrap.dedent(f"""
        const app = require({json.dumps(str(APP_JS))});
        app.state.data = {{
          groups: [{{ key: "cod", countries: [
            {{ name: "CHINA", volume: [1] }},
            {{ name: "Other", volume: [1], top_unlisted: [[
                {{ name: "INDIA", volume: 59475 }} ]] }},
          ] }}],
        }};
        app.state.activeKey = "cod";
        const items = [{{ dataset: {{ label: "Other" }}, dataIndex: 0 }}];
        const lines = app.shareTooltipAfterBody(items);
        console.log(JSON.stringify({{
          mentionsIndia: lines.some(l => l.includes("INDIA")),
          mentionsVolume: lines.some(l => l.includes("59.475") || l.includes("59475")),
        }}));
    """)
    result = run_node(script)
    assert result["mentionsIndia"] is True
    assert result["mentionsVolume"] is True


def test_render_other_note_leaves_no_element_when_no_outlier():
    script = textwrap.dedent(f"""
        const notes = {{}};
        const shareCard = {{ appendChild: (el) => {{ notes[el.id] = el; }} }};
        const elements = {{ "share-card": shareCard, "other-note": null }};
        global.document = {{
          getElementById: (id) => elements[id] || null,
          createElement: (tag) => ({{ tagName: tag, remove() {{}} }}),
        }};
        const app = require({json.dumps(str(APP_JS))});
        app.state.data = {{
          months: ["2026-06"],
          groups: [{{ key: "cod", label: "Cod", countries: [
            {{ name: "CHINA", volume: [999999999] }},
            {{ name: "Other", volume: [1], top_unlisted: [[
                {{ name: "INDIA", volume: 1 }} ]] }},
          ] }}],
        }};
        app.state.activeKey = "cod";
        app.renderOtherNote();
        console.log(JSON.stringify({{ appended: Object.keys(notes) }}));
    """)
    result = run_node(script)
    assert result["appended"] == []


def test_render_other_note_appends_note_when_outlier_exists():
    script = textwrap.dedent(f"""
        const notes = {{}};
        const shareCard = {{ appendChild: (el) => {{ notes[el.id] = el; }} }};
        const elements = {{ "share-card": shareCard, "other-note": null }};
        global.document = {{
          getElementById: (id) => elements[id] || null,
          createElement: (tag) => ({{ tagName: tag, remove() {{}} }}),
        }};
        const app = require({json.dumps(str(APP_JS))});
        app.state.data = {{
          months: ["2026-06"],
          groups: [{{ key: "haddock", label: "Haddock", countries: [
            {{ name: "NORWAY", volume: [5462] }},
            {{ name: "CANADA", volume: [5410] }},
            {{ name: "Other", volume: [99999], top_unlisted: [[
                {{ name: "THAILAND", volume: 54564 }} ]] }},
          ] }}],
        }};
        app.state.activeKey = "haddock";
        app.renderOtherNote();
        const text = notes["other-note"] ? notes["other-note"].textContent : "";
        console.log(JSON.stringify({{
          appended: Object.keys(notes),
          mentionsThailand: text.includes("THAILAND"),
        }}));
    """)
    result = run_node(script)
    assert result["appended"] == ["other-note"]
    assert result["mentionsThailand"] is True


def test_switching_to_group_without_countries_removes_stale_other_note():
    """Regression: renderShareChart's early-return branch (no countries,
    e.g. Salmon) must also clear any other-note left over from the
    previously active group — otherwise a stale note about a DIFFERENT
    group's Other lingers under a hidden share-card."""
    script = textwrap.dedent(f"""
        const staleNote = {{ id: "other-note", removed: false, remove() {{ this.removed = true; }} }};
        const elements = {{
          "share-card": {{ hidden: false }},
          "chart-share": {{ getContext: () => ({{}}) }},
          "other-note": staleNote,
        }};
        global.document = {{ getElementById: (id) => elements[id] }};
        global.getComputedStyle = () => ({{ getPropertyValue: () => "#000000" }});
        global.Chart = function (ctx, cfg) {{ this.destroy = () => {{}}; }};

        const app = require({json.dumps(str(APP_JS))});
        app.state.data = {{
          months: ["2026-01"],
          groups: [
            {{ key: "salmon", label: "Salmon", countries: [], volume: [1], asp: [1] }},
          ],
        }};
        app.state.activeKey = "salmon";
        app.renderShareChart();
        console.log(JSON.stringify({{ staleNoteRemoved: staleNote.removed }}));
    """)
    result = run_node(script)
    assert result["staleNoteRemoved"] is True
